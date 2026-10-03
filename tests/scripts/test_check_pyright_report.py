"""
Tests scripts/check_pyright_report.py
"""

import runpy
from collections.abc import Callable
from pathlib import Path

import pytest

CheckReport = Callable[..., list[str]]


@pytest.fixture(scope="module")
def check_report(tests_dir: Path) -> CheckReport:
    script_path = tests_dir.parent / "scripts" / "check_pyright_report.py"
    return runpy.run_path(str(script_path))["check_report"]


def test_no_failures_when_files_analyzed_without_errors(check_report: CheckReport):
    assert check_report({"summary": {"filesAnalyzed": 10, "errorCount": 0}}) == []


def test_fails_when_no_files_analyzed(check_report: CheckReport):
    (failure,) = check_report({"summary": {"filesAnalyzed": 0, "errorCount": 0}})
    assert "analyzed 0 files" in failure


def test_fails_when_errors_reported(check_report: CheckReport):
    (failure,) = check_report({"summary": {"filesAnalyzed": 10, "errorCount": 3}})
    assert "3 error(s)" in failure


def test_allows_pyright_diagnostic_status(check_report: CheckReport):
    report = {"summary": {"filesAnalyzed": 10, "errorCount": 0}}
    assert check_report(report, pyright_status=1) == []


def test_fails_when_pyright_itself_failed(check_report: CheckReport):
    report = {"summary": {"filesAnalyzed": 10, "errorCount": 0}}
    (failure,) = check_report(report, pyright_status=3)
    assert "exited with status 3" in failure
