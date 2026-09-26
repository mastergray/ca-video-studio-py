import pytest  # Assert configuration validation failures

from ca_video.config.models import ConfigError, defaultProject, parseProject  # Exercise project models


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
