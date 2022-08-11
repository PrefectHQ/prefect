import pytest

from prefect.settings import PREFECT_FEATURE_FLAGGING_ENABLED, temporary_settings
from prefect.testing.cli import invoke_and_assert
from prefect.utilities import feature_flags

ENABLE_NEW_PROFILES = "enable-new-profiles"
ENABLE_FANCY_DEPLOYMENTS = "enable-fancy-deployments"


@pytest.fixture
def disabled_flag():
    with temporary_settings(updates={PREFECT_FEATURE_FLAGGING_ENABLED: "true"}):
        flag = feature_flags.create_if_missing(ENABLE_NEW_PROFILES, is_enabled=False)
        yield flag
        flag.destroy()


@pytest.fixture
def enabled_flag():
    with temporary_settings(updates={PREFECT_FEATURE_FLAGGING_ENABLED: "true"}):
        flag = feature_flags.create_if_missing(
            ENABLE_FANCY_DEPLOYMENTS, is_enabled=True
        )
        yield flag
        flag.destroy()


def test_does_not_list_feature_flags_with_flags_disabled_globally(enabled_flag):
    with temporary_settings(updates={PREFECT_FEATURE_FLAGGING_ENABLED: "false"}):
        invoke_and_assert(
            command=["flag", "ls"],
            expected_output=f"""
Feature flagging is disabled because the PREFECT_FEATURE_FLAGGING_ENABLED setting is false.
        """,
            expected_code=0,
        )


def test_lists_enabled_feature_flags(enabled_flag):
    with temporary_settings(updates={PREFECT_FEATURE_FLAGGING_ENABLED: "true"}):
        invoke_and_assert(
            command=["flag", "ls"],
            expected_output=f"""
            Feature Flags:             
┏━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┓
┃ Name                     ┃ Enabled? ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━┩
│ enable-fancy-deployments │ True     │
└──────────────────────────┴──────────┘
        """,
            expected_code=0,
        )


def test_lists_disabled_feature_flags(disabled_flag):
    with temporary_settings(updates={PREFECT_FEATURE_FLAGGING_ENABLED: "true"}):
        invoke_and_assert(
            command=["flag", "ls"],
            expected_output=f"""
            Feature Flags:          
┏━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┓
┃ Name                ┃ Enabled? ┃
┡━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━┩
│ enable-new-profiles │ False    │
└─────────────────────┴──────────┘
        """,
            expected_code=0,
        )
