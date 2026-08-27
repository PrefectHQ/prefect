"""
Report on a pyright JSON report and fail if the run was not a clean, real run.

Pyright exits 0 when its configuration matches no files at all, so a
misconfigured `include` silently turns the CI check into a no-op. Running with
`--outputjson` and checking the summary here catches that case.

Usage: python scripts/check_pyright_report.py <report.json> [--pyright-status N]
"""

import argparse
import json
import sys
from typing import Any

# pyright exits 0 with no diagnostics and 1 when it reports diagnostics; anything
# higher is a pyright failure, e.g. a config file that cannot be parsed
MAX_EXPECTED_PYRIGHT_STATUS = 1


def format_diagnostic(diagnostic: dict[str, Any]) -> str:
    start = diagnostic.get("range", {}).get("start", {})
    location = f"{diagnostic.get('file', 'unknown file')}:{start.get('line', 0) + 1}:{start.get('character', 0) + 1}"
    rule = diagnostic.get("rule")
    message = diagnostic.get("message", "")
    return f"{location} - {diagnostic.get('severity', 'error')}: {message}" + (
        f" ({rule})" if rule else ""
    )


def check_report(report: dict[str, Any], pyright_status: int = 0) -> list[str]:
    """Return the reasons the pyright run should be considered a failure."""
    failures: list[str] = []

    if pyright_status > MAX_EXPECTED_PYRIGHT_STATUS:
        failures.append(f"pyright exited with status {pyright_status}")

    summary = report.get("summary", {})
    if not summary.get("filesAnalyzed"):
        failures.append(
            "pyright analyzed 0 files; check that the paths in the pyright config "
            "resolve relative to the config file's directory"
        )

    if summary.get("errorCount"):
        failures.append(f"pyright reported {summary['errorCount']} error(s)")

    return failures


def main(report_path: str, pyright_status: int) -> int:
    with open(report_path) as f:
        report = json.load(f)

    for diagnostic in report.get("generalDiagnostics", []):
        print(format_diagnostic(diagnostic))

    print(json.dumps(report.get("summary", {}), indent=2))

    failures = check_report(report, pyright_status)
    for failure in failures:
        print(f"error: {failure}", file=sys.stderr)

    return 1 if failures else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", help="path to a pyright --outputjson report")
    parser.add_argument(
        "--pyright-status",
        type=int,
        default=0,
        help="exit status of the pyright run that produced the report",
    )
    args = parser.parse_args()

    sys.exit(main(args.report, args.pyright_status))
