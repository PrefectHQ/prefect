import importlib.util
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "report_api_compatibility", SCRIPTS / "report_api_compatibility.py"
)
reporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reporter)


@pytest.fixture
def results(tmp_path: Path) -> Path:
    for revision in ("base", "head"):
        directory = tmp_path / revision
        directory.mkdir()
        write_results(directory, {})
    return tmp_path


def write_results(
    directory: Path, failures: dict[str, str], status: int | None = None
) -> None:
    suite = ET.Element("testsuite")
    ET.SubElement(suite, "testcase", name="passing_test")
    for name, message in failures.items():
        case = ET.SubElement(suite, "testcase", name=name)
        ET.SubElement(case, "failure", message=message)
    ET.ElementTree(suite).write(directory / "pytest.xml")
    (directory / "status").write_text(
        str(int(bool(failures)) if status is None else status)
    )


def test_existing_failures_do_not_warn(results: Path):
    for revision in ("base", "head"):
        write_results(
            results / revision, {"test_sort[TaskRunSort]": "AssertionError: duration"}
        )
    report = reporter.compare_results(results)
    assert report["status"] == "compatible"
    assert report["new_failures"] == []
    assert report["base_failures"] == report["head_failures"] == 1


def test_new_and_changed_failures_warn(results: Path):
    write_results(
        results / "base", {"test_sort[TaskRunSort]": "AssertionError: duration"}
    )
    write_results(
        results / "head",
        {
            "test_sort[TaskRunSort]": "AssertionError: duration, new_sort",
            "test_route[POST: /api/new]": "AssertionError: missing endpoint",
        },
    )
    report = reporter.compare_results(results)
    assert report["status"] == "incompatible"
    assert report["new_failures"] == [
        "test_route[POST: /api/new]",
        "test_sort[TaskRunSort]",
    ]


def test_resolved_failures_do_not_warn(results: Path):
    write_results(results / "base", {"test_sort": "AssertionError: duration"})
    assert reporter.compare_results(results)["status"] == "compatible"


@pytest.mark.parametrize("revision", ["base", "head"])
@pytest.mark.parametrize(
    "failure",
    [
        "missing",
        "invalid_xml",
        "collection",
        "harness",
        "empty",
        "inconsistent",
        "error",
    ],
)
def test_incomplete_checks_are_unavailable(results: Path, revision: str, failure: str):
    directory = results / revision
    if failure == "missing":
        (directory / "pytest.xml").unlink()
    elif failure == "invalid_xml":
        (directory / "pytest.xml").write_text("not xml")
    elif failure == "collection":
        (directory / "status").write_text("2")
    elif failure == "harness":
        write_results(directory, {"test_route": "KeyError: tags"})
    elif failure == "empty":
        (directory / "pytest.xml").write_text("<testsuite/>")
    elif failure == "inconsistent":
        write_results(directory, {"test_sort": "AssertionError: duration"}, status=0)
    else:
        write_results(directory, {"test_sort": "AssertionError: duration"})
        root = ET.parse(directory / "pytest.xml")
        ET.SubElement(root.getroot(), "error", message="fixture failed")
        root.write(directory / "pytest.xml")
    assert reporter.compare_results(results)["status"] == "unavailable"


def test_cli_preserves_the_advisory_result(results: Path):
    write_results(results / "head", {"test_route": "AssertionError: new endpoint"})
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "report_api_compatibility.py"), str(results)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "::warning::" in result.stdout
    assert json.loads((results / "report.json").read_text())["status"] == "incompatible"


@pytest.mark.parametrize("compatibility", [False, True])
def test_schema_generation_preserves_the_ui_contract(
    tmp_path: Path, compatibility: bool
):
    command = [sys.executable, str(SCRIPTS / "generate_oss_openapi_schema.py")]
    if compatibility:
        command.append("--api-compatibility")
    subprocess.run(command, cwd=tmp_path, check=True, capture_output=True, text=True)
    schema = json.loads((tmp_path / "oss_schema.json").read_text())
    if compatibility:
        assert "/api/flows/" in schema["paths"]
        assert "/api/ui-settings" not in schema["paths"]
        assert "UISettings" not in schema["components"]["schemas"]
        assert all(path.startswith("/api/") for path in schema["paths"])
    else:
        assert "/flows/" in schema["paths"]
        assert "/ui-settings" in schema["paths"]
        assert "UISettings" in schema["components"]["schemas"]
