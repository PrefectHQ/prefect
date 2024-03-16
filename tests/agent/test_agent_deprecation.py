import pytest

from prefect._internal.compatibility.deprecated import PrefectDeprecationWarning
from prefect.agent import PrefectAgent


def test_agent_emits_deprecation_warning():
    with pytest.warns(
        PrefectDeprecationWarning,
        match=(
            "prefect.agent.PrefectAgent has been deprecated. It will not be available after Sep 2024. Use a worker instead. Refer to the upgrade guide for more information"
        ),
    ):
        PrefectAgent()
