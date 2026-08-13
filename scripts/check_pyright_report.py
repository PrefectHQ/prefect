"""
Report on a pyright JSON report and fail if it found errors or analyzed no files.

Pyright exits 0 when its configuration matches no files at all, so a
misconfigured `include` silently turns the CI check into a no-op. Running with
`--outputjson` and checking the summary here catches that case.

Usage: python scripts/check_pyright_report.py <report.json>
"""

import json
import sys
from typing import Any


def format_diagnostic(diagnostic: dict[str, Any]) -> str:
    start = diagnostic.get("range", {}).get("start", {})
    location = f"{diagnostic.get('file', 'unknown file')}:{start.get('line', 0) + 1}:{start.get('character', 0) + 1}"
    rule = diagnostic.get("rule")
    message = diagnostic.get("message", "")
    return f"{location} - {diagnostic.get('severity', 'error')}: {message}" + (
        f" ({rule})" if rule else ""
    )


def check_report(report: dict[str, Any]) -> list[str]:
    """Return the reasons the pyright run should be considered a failure."""
    failures: list[str] = []

    summary = report.get("summary", {})
    if not summary.get("filesAnalyzed"):
        failures.append(
            "pyright analyzed 0 files; check that the paths in the pyright config "
            "resolve relative to the config file's directory"
        )

    if summary.get("errorCount"):
        failures.append(f"pyright reported {summary['errorCount']} error(s)")

    return failures


def main(report_path: str) -> int:
    with open(report_path) as f:
        report = json.load(f)

    for diagnostic in report.get("generalDiagnostics", []):
        print(format_diagnostic(diagnostic))

    print(json.dumps(report.get("summary", {}), indent=2))

    failures = check_report(report)
    for failure in failures:
        print(f"error: {failure}", file=sys.stderr)

    return 1 if failures else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/check_pyright_report.py <report.json>")
        sys.exit(1)

    sys.exit(main(sys.argv[1]))
