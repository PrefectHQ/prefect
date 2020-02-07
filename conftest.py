import sys

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--skip-formatting",
        action="store_true",
        dest="formatting",
        help="including this flag will skip all formatting tests",
    )


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "formatting: mark test as formatting to skip when --skip-formatting flag is provided.",
    )


def pytest_runtest_setup(item):
    formatting_mark = item.get_closest_marker("formatting")

    # if a test IS marked as "formatting" and the --skip-formatting flag IS set, skip it
    if (
        formatting_mark is not None
        and item.config.getoption("--skip-formatting") is True
    ):
        pytest.skip(
            "Formatting tests skipped because --skip-formatting flag was provided."
        )
