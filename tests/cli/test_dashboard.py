from unittest.mock import MagicMock

import pytest

from prefect.settings import (
    PREFECT_UI_URL,
    temporary_settings,
)
from prefect.testing.cli import invoke_and_assert


@pytest.fixture
def mock_webbrowser(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    mock = MagicMock()
    monkeypatch.setattr("prefect.cli.dashboard.webbrowser", mock)
    return mock


def test_open_dashboard_in_browser_success(mock_webbrowser: MagicMock) -> None:
    invoke_and_assert(
        ["dashboard", "open"],
        expected_code=0,
        expected_output_contains=f"Opened {PREFECT_UI_URL.value()!r} in browser.",
    )

    mock_webbrowser.open_new_tab.assert_called_with(PREFECT_UI_URL.value())


def test_open_dashboard_in_browser_failure_no_ui_url(
    mock_webbrowser: MagicMock,
) -> None:
    with temporary_settings({PREFECT_UI_URL: ""}):
        invoke_and_assert(
            ["dashboard", "open"],
            expected_code=1,
            expected_output_contains="PREFECT_UI_URL` must be set",
        )

        mock_webbrowser.open_new_tab.assert_not_called()
