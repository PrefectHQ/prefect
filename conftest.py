import sys

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--airflow",
        action="store_true",
        dest="airflow",
        help="including this flag will attempt to ONLY run airflow compatibility tests",
    )
    parser.addoption(
        "--skip-formatting",
        action="store_true",
        dest="formatting",
        help="including this flag will skip all formatting tests",
    )


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "airflow: mark test to run only when --airflow flag is provided."
    )
    config.addinivalue_line(
        "markers",
        "formatting: mark test as formatting to skip when --skip-formatting flag is provided.",
    )


def pytest_runtest_setup(item):
    air_mark = item.get_closest_marker("airflow")

    # if a test IS marked as "airflow" and the airflow flag IS NOT set, skip it
    if air_mark is not None and item.config.getoption("--airflow") is False:
        pytest.skip(
            "Airflow tests skipped by default unless --airflow flag provided to pytest."
        )

    # if a test IS NOT marked as airflow and the airflow flag IS set, skip it
    elif air_mark is None and item.config.getoption("--airflow") is True:
        pytest.skip("Non-Airflow tests skipped because --airflow flag was provided.")

    formatting_mark = item.get_closest_marker("formatting")

    # if a test IS marked as "formatting" and the --skip-formatting flag IS set, skip it
    if (
        formatting_mark is not None
        and item.config.getoption("--skip-formatting") is True
    ):
        pytest.skip(
            "Formatting tests skipped because --skip-formatting flag was provided."
        )
