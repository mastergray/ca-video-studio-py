import json  # Inspect normalized persisted project data

import pytest  # Assert configuration validation failures

from ca_video.config.models import (  # Exercise project parsing and persistence
    ConfigError,
    defaultProject,
    loadProject,
    parseProject,
    saveProject,
)


def test_default_project_has_exact_frame_count() -> None:
    project = defaultProject()
    assert project.output.totalFrames == 150
    assert project.output.width * 9 == project.output.height * 16


def test_layer_fade_rate_round_trips_and_zero_is_omitted() -> None:
    data = defaultProject().toDict()
    data["layers"][0]["render"]["fade_rate"] = 6.5

    project = parseProject(data)

    assert project.layer.fadeRate == 6.5
    assert project.toDict()["layers"][0]["render"]["fade_rate"] == 6.5
    data["layers"][0]["render"]["fade_rate"] = 0
    assert "fade_rate" not in parseProject(data).toDict()["layers"][0]["render"]


def test_layer_fade_rate_is_limited_to_reference_range() -> None:
    data = defaultProject().toDict()
    data["layers"][0]["render"]["fade_rate"] = 51

    with pytest.raises(ConfigError, match="between 0 and 50"):
        parseProject(data)


def test_non_integral_frame_count_is_rejected() -> None:
    project = defaultProject()
    invalid = project.output.withOverrides(durationSeconds=1.01)
    with pytest.raises(ConfigError, match="must be an integer"):
        _ = invalid.totalFrames


def test_unknown_fields_are_rejected() -> None:
    with pytest.raises(ConfigError, match="unsupported field"):
        parseProject({"schema_version": 1, "surprise": True})


def test_custom_rule_and_initializer_round_trip(tmp_path) -> None:
    data = defaultProject(tmp_path).toDict()
    layer = data["layers"][0]
    layer["simulation"]["rule"] = {"notation": "B2/S/C3", "neighborhood": "von_neumann"}
    layer["simulation"]["initial"] = {
        "type": "cells",
        "origin": "center",
        "cells": [[0, 0], [1, 0]],
    }
    project = parseProject(data, tmp_path)
    destination = tmp_path / "custom.cav.json"

    saveProject(project, destination)
    loaded = loadProject(destination)

    assert loaded.layer.rule.notation == "B2/S/C3"
    assert loaded.layer.rule.neighborhood == "von_neumann"
    assert loaded.layer.initial.cells == ((0, 0), (1, 0))
    assert json.loads(destination.read_text(encoding="utf-8")) == loaded.toDict()


def test_every_catalog_preset_is_accepted() -> None:
    from ca_video.catalogs.rules_2d import ruleCatalog  # Keep test dependency local and explicit

    for entry in ruleCatalog():
        data = defaultProject().toDict()
        data["layers"][0]["simulation"]["rule"] = {"preset": entry.key}
        assert parseProject(data).layer.rulePreset == entry.key


def test_initializer_must_fit_the_grid() -> None:
    data = defaultProject().toDict()
    data["layers"][0]["simulation"]["initial"] = {
        "type": "disc",
        "density": 1,
        "radius": 100,
    }
    with pytest.raises(ConfigError, match="too large"):
        parseProject(data)


def test_multiple_layers_round_trip_and_require_unique_ids() -> None:
    data = defaultProject().toDict()
    second = json.loads(json.dumps(data["layers"][0]))
    second["id"] = "second"
    second["name"] = "Second Layer"
    second["z_index"] = 1
    data["layers"].append(second)

    project = parseProject(data)
    assert [layer.id for layer in project.layers] == ["life", "second"]
    assert len(parseProject(project.toDict()).layers) == 2

    data["layers"][1]["id"] = "life"
    with pytest.raises(ConfigError, match="unique"):
        parseProject(data)


def test_optional_layer_seed_round_trips_and_is_bounded() -> None:
    data = defaultProject().toDict()
    data["layers"][0]["seed"] = 9_223_372_036_854_775_807
    project = parseProject(data)
    assert project.layer.seed == 9_223_372_036_854_775_807
    assert project.toDict()["layers"][0]["seed"] == 9_223_372_036_854_775_807

    data["layers"][0]["seed"] += 1
    with pytest.raises(ConfigError, match="between 0"):
        parseProject(data)


def test_cell_size_grid_round_trips_and_tracks_export_resolution() -> None:
    data = defaultProject().toDict()
    data["layers"][0]["simulation"]["grid"] = {
        "cell_size_px": 8,
        "boundary": "wrap",
    }
    project = parseProject(data)

    assert project.layer.cellSizePx == 8
    assert (project.layer.gridWidth, project.layer.gridHeight) == (80, 45)
    assert project.toDict()["layers"][0]["simulation"]["grid"]["cell_size_px"] == 8

    resized = project.toDict()
    resized["output"].update({"width": 1920, "height": 1080})
    resizedProject = parseProject(resized)
    assert (resizedProject.layer.gridWidth, resizedProject.layer.gridHeight) == (240, 135)


def test_wolfram_layer_round_trips_without_outer_totalistic_fields(tmp_path) -> None:
    data = defaultProject(tmp_path).toDict()
    data["layers"][0]["simulation"] = {
        "mode": "wolfram_2d",
        "grid": {"size": [40, 24], "boundary": "wrap"},
        "rule": {"number": 110},
        "initial": {"type": "bits", "bits": [1, 0, 1, 1]},
    }
    project = parseProject(data, tmp_path)
    destination = tmp_path / "wolfram.cav.json"

    saved = saveProject(project, destination)

    assert saved.layer.simulationMode == "wolfram_2d"
    assert saved.layer.wolframRule == 110
    assert saved.layer.rule is None
    assert saved.layer.initial.bits == (1, 0, 1, 1)
    assert saved.toDict()["layers"][0]["simulation"] == data["layers"][0]["simulation"]


def test_wolfram_layer_requires_wrapping_and_family_specific_fields() -> None:
    data = defaultProject().toDict()
    simulation = data["layers"][0]["simulation"]
    simulation.update(
        {
            "mode": "wolfram_2d",
            "grid": {"size": [40, 24], "boundary": "fixed"},
            "rule": {"number": 30},
            "initial": {"type": "single_center"},
        }
    )
    with pytest.raises(ConfigError, match="wrapped horizontal boundary"):
        parseProject(data)

    simulation["grid"]["boundary"] = "wrap"
    simulation["rule"] = {"number": 30, "preset": "life"}
    with pytest.raises(ConfigError, match="unsupported field"):
        parseProject(data)


def test_wolfram_random_row_defaults_to_half_density() -> None:
    data = defaultProject().toDict()
    data["layers"][0]["simulation"] = {
        "mode": "wolfram_2d",
        "grid": {"size": [40, 24], "boundary": "wrap"},
        "rule": {"number": 90},
        "initial": {"type": "random"},
    }

    project = parseProject(data)

    assert project.layer.initial.density == 0.5
    assert project.toDict()["layers"][0]["simulation"]["initial"]["density"] == 0.5


def test_geometric_pixel_offset_round_trips_and_is_type_specific(tmp_path) -> None:
    data = defaultProject(tmp_path).toDict()
    initial = data["layers"][0]["simulation"]["initial"]
    initial.update({"type": "disc", "radius": 8, "offset_px": [120, -64]})

    project = parseProject(data, tmp_path)
    loaded = saveProject(project, tmp_path / "offset.cav.json")

    assert loaded.layer.initial.offsetPx == (120, -64)
    assert loaded.toDict()["layers"][0]["simulation"]["initial"]["offset_px"] == [120, -64]

    initial.update({"type": "random"})
    with pytest.raises(ConfigError, match="supported only"):
        parseProject(data, tmp_path)


def test_3d_layer_round_trips_with_normalized_catalog_initializer(tmp_path) -> None:
    data = defaultProject(tmp_path).toDict()
    data["layers"][0] = {
        "id": "voxels",
        "name": "Voxels",
        "dimension": "3d",
        "simulation": {
            "mode": "outer_totalistic",
            "grid": {"grid_size": 24, "boundary": "fixed"},
            "rule": {"preset": "445"},
            "initial": {"type": "catalog_default"},
        },
        "render": {
            "style": "isometric_voxel",
            "palette": "445",
            "voxel_scale": "auto",
            "surface_only": True,
        },
    }

    project = parseProject(data, tmp_path)
    loaded = saveProject(project, tmp_path / "voxels.cav.json")

    assert loaded.layer.dimension == "3d"
    assert loaded.layer.gridSize == 24
    assert loaded.layer.initial.type == "sphere"
    assert loaded.layer.initial.density == 0.5
    assert loaded.layer.voxelScale == 0
    assert loaded.toDict()["layers"][0]["render"]["voxel_scale"] == "auto"


def test_mixed_2d_and_3d_layers_parse_together() -> None:
    data = defaultProject().toDict()
    data["layers"].append(
        {
            "id": "crystal",
            "name": "Crystal",
            "dimension": "3d",
            "z_index": 1,
            "simulation": {
                "mode": "outer_totalistic",
                "grid": {"grid_size": 16, "boundary": "fixed"},
                "rule": {"preset": "crystal"},
                "initial": {"type": "cross"},
            },
            "render": {"style": "isometric_voxel", "palette": "crystal"},
        }
    )

    project = parseProject(data)

    assert [layer.dimension for layer in project.layers] == ["2d", "3d"]
    assert parseProject(project.toDict()).layers[1].rulePreset == "crystal"


def test_projected_camera_and_render_controls_round_trip() -> None:
    data = defaultProject().toDict()
    data["camera"].update(
        {
            "azimuth_deg": 42,
            "elevation_deg": 20,
            "rotation_deg_per_second": -15,
        }
    )
    data["layers"][0] = {
        "id": "projected",
        "name": "Projected",
        "dimension": "3d",
        "simulation": {
            "mode": "outer_totalistic",
            "grid": {"grid_size": 20, "boundary": "fixed"},
            "rule": {"preset": "crystal"},
            "initial": {"type": "cross", "offset_cells": [3, -2, 1]},
        },
        "render": {
            "style": "projected_voxel",
            "palette": "crystal",
            "color_by": "distance",
            "fade_rate": 8,
            "voxel_scale": 7,
            "surface_only": True,
            "depth_shading": False,
            "vignette": True,
            "camera": {"zoom": 1.4, "pan_x": 0.2},
        },
    }

    project = parseProject(data)
    normalized = parseProject(project.toDict())

    assert normalized.camera.azimuthDeg == 42
    assert normalized.layer.renderStyle == "projected_voxel"
    assert normalized.layer.colorBy == "distance"
    assert normalized.layer.camera.zoom == 1.4
    assert normalized.layer.camera.panX == 0.2
    assert normalized.layer.camera.elevationDeg == 20
    assert normalized.layer.fadeRate == 8
    assert normalized.layer.initial.offsetCells == (3, -2, 1)
    assert normalized.toDict()["layers"][0]["simulation"]["initial"]["offset_cells"] == [3, -2, 1]
    assert not normalized.layer.depthShading
    assert normalized.layer.vignette

    data["layers"][0]["simulation"]["initial"]["offset_cells"] = [0, 0, 0]
    zeroOffset = parseProject(data).toDict()["layers"][0]["simulation"]["initial"]
    assert "offset_cells" not in zeroOffset


def test_isometric_style_rejects_projected_only_controls() -> None:
    data = defaultProject().toDict()
    layer = {
        "id": "voxels",
        "name": "Voxels",
        "dimension": "3d",
        "simulation": {
            "mode": "outer_totalistic",
            "grid": {"grid_size": 16, "boundary": "fixed"},
            "rule": {"preset": "445"},
            "initial": {"type": "single"},
        },
        "render": {
            "style": "isometric_voxel",
            "palette": "445",
            "color_by": "height",
        },
    }
    data["layers"][0] = layer

    with pytest.raises(ConfigError, match="projected render controls"):
        parseProject(data)


def test_wolfram_3d_extrusion_round_trips_family_specific_fields() -> None:
    data = defaultProject().toDict()
    data["layers"][0] = {
        "id": "wolfram_3d",
        "name": "Wolfram 3D",
        "dimension": "3d",
        "simulation": {
            "mode": "wolfram_3d_extruded",
            "grid": {"grid_size": 24, "boundary": "fixed"},
            "rule": {"number": 110},
            "initial": {"type": "bits", "bits": [1, 0, 1, 1]},
            "extrusion_depth": 7,
            "extrusion_offset": -4,
        },
        "render": {
            "style": "projected_voxel",
            "palette": "wolfram3d",
            "color_by": "height",
            "surface_only": True,
        },
    }

    project = parseProject(data)
    normalized = parseProject(project.toDict())

    assert normalized.layer.simulationMode == "wolfram_3d_extruded"
    assert normalized.layer.wolframRule == 110
    assert normalized.layer.rule is None
    assert normalized.layer.rulePreset is None
    assert normalized.layer.initial.bits == (1, 0, 1, 1)
    assert normalized.layer.extrusionDepth == 7
    assert normalized.layer.extrusionOffset == -4
    assert normalized.layer.palette == "wolfram3d"

    data["layers"][0]["simulation"]["extrusion_offset"] = 0
    zeroOffset = parseProject(data).toDict()["layers"][0]["simulation"]
    assert "extrusion_offset" not in zeroOffset


def test_3d_offsets_are_limited_to_their_supported_initializers() -> None:
    data = defaultProject().toDict()
    data["layers"][0] = {
        "id": "voxels",
        "name": "Voxels",
        "dimension": "3d",
        "simulation": {
            "mode": "outer_totalistic",
            "grid": {"grid_size": 16, "boundary": "fixed"},
            "rule": {"preset": "445"},
            "initial": {"type": "random", "offset_cells": [1, 0, 0]},
        },
        "render": {"style": "isometric_voxel", "palette": "445"},
    }

    with pytest.raises(ConfigError, match="geometric 3D initializers"):
        parseProject(data)


def test_wolfram_3d_requires_fixed_volume_and_fitting_extrusion() -> None:
    data = defaultProject().toDict()
    data["layers"][0] = {
        "id": "wolfram_3d",
        "name": "Wolfram 3D",
        "dimension": "3d",
        "simulation": {
            "mode": "wolfram_3d_extruded",
            "grid": {"grid_size": 16, "boundary": "wrap"},
            "rule": {"number": 30},
            "initial": {"type": "single_center"},
        },
        "render": {"style": "isometric_voxel", "palette": "wolfram3d"},
    }
    with pytest.raises(ConfigError, match="fixed volume"):
        parseProject(data)

    data["layers"][0]["simulation"]["grid"]["boundary"] = "fixed"
    data["layers"][0]["simulation"]["extrusion_depth"] = 17
    with pytest.raises(ConfigError, match="between 1 and 16"):
        parseProject(data)
