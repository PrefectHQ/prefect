import pytest

from prefect.testing.cli import invoke_and_assert
from prefect.utilities import feature_flags

ENABLE_NEW_PROFILES = "enable-new-profiles"


@pytest.fixture
def flags():
    yield feature_flags.create_if_missing(ENABLE_NEW_PROFILES)


def test_lists_feature_flags(flags):
    invoke_and_assert(
        command=["flags", "ls"],
        expected_output=f"""
  Feature Flags:   
┏━━━━━━┳━━━━━━━━━━┓
┃ Name ┃ Enabled? ┃
┡━━━━━━╇━━━━━━━━━━┩
└──────┴──────────┘
        """,
        expected_code=0,
    )
