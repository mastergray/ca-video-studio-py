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
