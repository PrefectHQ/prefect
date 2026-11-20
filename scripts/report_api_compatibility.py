"""Report newly observed shared-suite failures against one Cloud schema snapshot."""

import argparse
import hashlib
import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path


def read_results(directory: Path) -> tuple[int, dict[tuple[str, str], str]]:
    """Read completed pytest results and fingerprint their assertion failures."""
    status = int((directory / "status").read_text())
    root = ET.parse(directory / "pytest.xml").getroot()
    cases = list(root.iter("testcase"))
    if status not in (0, 1) or not cases or root.find(".//error") is not None:
        raise ValueError(f"{directory.name} compatibility tests did not complete")
    failures = {}
    for case in cases:
        failure = case.find("failure")
        if failure is None:
            continue
        message = failure.get("message", "")
        if not message.startswith("AssertionError"):
            raise ValueError(f"{directory.name} tests encountered a harness error")
        # A changed failure in an already-failing test still needs attention.
        digest = hashlib.sha256(message.encode()).hexdigest()
        name = case.attrib["name"]
        failures[name, digest] = name
    if bool(status) != bool(failures):
        raise ValueError(f"{directory.name} exit status disagrees with its report")
    return len(cases), failures


def compare_results(directory: Path) -> dict:
    """Exclude unchanged base failures and distinguish incomplete checks."""
    try:
        base_count, base = read_results(directory / "base")
        head_count, head = read_results(directory / "head")
    except (OSError, ValueError, ET.ParseError) as exc:
        return {"status": "unavailable", "reason": str(exc)}
    new_failures = sorted(head[key] for key in head.keys() - base.keys())
    return {
        "status": "incompatible" if new_failures else "compatible",
        "base_tests": base_count,
        "head_tests": head_count,
        "base_failures": len(base),
        "head_failures": len(head),
        "new_failures": new_failures,
    }


def main() -> int:
    """Write the comparison report and return its advisory exit status."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    args.directory.mkdir(parents=True, exist_ok=True)
    report = compare_results(args.directory)
    (args.directory / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    if report["status"] == "unavailable":
        summary = "Cloud API compatibility could not be evaluated. See the test logs."
    else:
        summary = (
            f"Cloud API compatibility: {len(report['new_failures'])} new failures "
            f"({report['base_failures']} on base, {report['head_failures']} on head)."
        )
    print(summary)
    if summary_path := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(summary_path, "a") as output:
            output.write(summary + "\n")
    if report["status"] != "compatible":
        print(f"::warning::{summary}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
