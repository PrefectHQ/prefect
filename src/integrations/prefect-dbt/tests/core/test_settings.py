from pathlib import Path

from dbt_common.events.base_types import EventLevel
from prefect_dbt.core.settings import PrefectDbtSettings
from pytest import MonkeyPatch


def test_default_settings():
    settings = PrefectDbtSettings()
    assert settings.profiles_dir == Path.home() / ".dbt"
    assert settings.project_dir == Path.cwd()
    assert settings.log_level == EventLevel.INFO


def test_custom_settings():
    custom_profiles_dir = Path("/custom/profiles/dir")
    custom_project_dir = Path("/custom/project/dir")

    settings = PrefectDbtSettings(
        profiles_dir=custom_profiles_dir, project_dir=custom_project_dir
    )

    assert settings.profiles_dir == custom_profiles_dir
    assert settings.project_dir == custom_project_dir


def test_env_var_override(monkeypatch: MonkeyPatch):
    env_profiles_dir = "/env/profiles/dir"
    env_project_dir = "/env/project/dir"

    monkeypatch.setenv("DBT_PROFILES_DIR", env_profiles_dir)
    monkeypatch.setenv("DBT_PROJECT_DIR", env_project_dir)

    settings = PrefectDbtSettings()

    assert settings.profiles_dir == Path(env_profiles_dir)
    assert settings.project_dir == Path(env_project_dir)
