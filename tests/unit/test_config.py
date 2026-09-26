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
