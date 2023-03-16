import pytest

from prefect.settings import SETTING_VARIABLES, Setting


@pytest.fixture(autouse=True)
def prefect_experimental_test_setting(monkeypatch):
    """
    Injects a new setting for the TEST feature group.
    """
    PREFECT_EXPERIMENTAL_WARN_TEST = Setting(bool, default=False)
    PREFECT_EXPERIMENTAL_WARN_TEST.name = "PREFECT_EXPERIMENTAL_WARN_TEST"
    monkeypatch.setitem(
        SETTING_VARIABLES,
        "PREFECT_EXPERIMENTAL_WARN_TEST",
        PREFECT_EXPERIMENTAL_WARN_TEST,
    )
    monkeypatch.setattr(
        "prefect.settings.Settings.PREFECT_EXPERIMENTAL_WARN_TEST", True, raising=False
    )

    yield PREFECT_EXPERIMENTAL_WARN_TEST


@pytest.fixture
def disable_prefect_experimental_test_setting(
    monkeypatch, prefect_experimental_test_setting
):
    monkeypatch.setattr(
        "prefect.settings.Settings.PREFECT_EXPERIMENTAL_WARN_TEST", False, raising=False
    )


@pytest.fixture(autouse=True)
def prefect_experimental_test_opt_in_setting(monkeypatch):
    """
    Injects a new opt-in setting for the TEST feature group.
    """
    PREFECT_EXPERIMENTAL_ENABLE_TEST = Setting(bool, default=False)
    PREFECT_EXPERIMENTAL_ENABLE_TEST.name = "PREFECT_EXPERIMENTAL_ENABLE_TEST"
    monkeypatch.setitem(
        SETTING_VARIABLES,
        "PREFECT_EXPERIMENTAL_ENABLE_TEST",
        PREFECT_EXPERIMENTAL_ENABLE_TEST,
    )
    monkeypatch.setattr(
        "prefect.settings.Settings.PREFECT_EXPERIMENTAL_ENABLE_TEST",
        False,
        raising=False,
    )

    yield PREFECT_EXPERIMENTAL_ENABLE_TEST


@pytest.fixture
def enable_prefect_experimental_test_opt_in_setting(
    monkeypatch, prefect_experimental_test_opt_in_setting
):
    monkeypatch.setattr(
        "prefect.settings.Settings.PREFECT_EXPERIMENTAL_ENABLE_TEST",
        True,
        raising=False,
    )
