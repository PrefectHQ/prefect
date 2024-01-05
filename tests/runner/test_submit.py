import pytest

from prefect import flow
from prefect.runner import (
    submit_to_runner,
)
from prefect.settings import (
    PREFECT_EXPERIMENTAL_ENABLE_EXTRA_RUNNER_ENDPOINTS,
    PREFECT_RUNNER_SERVER_ENABLE,
    temporary_settings,
)


@flow
def schleeb() -> int:
    return 42


@pytest.fixture(autouse=True)
def runner_settings():
    with temporary_settings(
        {
            PREFECT_RUNNER_SERVER_ENABLE: True,
            PREFECT_EXPERIMENTAL_ENABLE_EXTRA_RUNNER_ENDPOINTS: True,
        }
    ):
        yield


def test_submission_raises_if_extra_endpoints_not_enabled():
    with temporary_settings(
        {PREFECT_EXPERIMENTAL_ENABLE_EXTRA_RUNNER_ENDPOINTS: False}
    ):
        with pytest.raises(
            ValueError,
            match="`submit_to_runner` utility requires the `Runner` webserver",
        ):
            submit_to_runner(lambda: None)


def test_submission_fails_over_if_webserver_is_not_running(caplog):
    expected_text = "The `submit_to_runner` utility failed to connect to the `Runner` webserver, but blocking failover is enabled."  # noqa
    with caplog.at_level("WARNING", logger="prefect.webserver"), temporary_settings(
        {
            PREFECT_RUNNER_SERVER_ENABLE: False,
        }
    ):
        result = submit_to_runner(schleeb)

        assert result == 42
        assert expected_text in caplog.text
