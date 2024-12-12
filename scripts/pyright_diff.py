import json
import sys
from typing import Any, Dict, NamedTuple


class Diagnostic(NamedTuple):
    """Structured representation of a diagnostic for easier table formatting."""

    file: str
    line: int
    character: int
    severity: str
    message: str


def normalize_diagnostic(diagnostic: Dict[Any, Any]) -> Dict[Any, Any]:
    """Normalize a diagnostic by removing or standardizing volatile fields."""
    normalized = diagnostic.copy()
    normalized.pop("time", None)
    normalized.pop("version", None)
    return normalized


def load_and_normalize_file(file_path: str) -> Dict[Any, Any]:
    """Load a JSON file and normalize its contents."""
    with open(file_path, "r") as f:
        data = json.load(f)
    return normalize_diagnostic(data)


def parse_diagnostic(diag: Dict[Any, Any]) -> Diagnostic:
    """Convert a diagnostic dict into a Diagnostic object."""
    file = diag.get("file", "unknown_file")
    message = diag.get("message", "no message")
    range_info = diag.get("range", {})
    start = range_info.get("start", {})
    line = start.get("line", 0)
    char = start.get("character", 0)
    severity = diag.get("severity", "unknown")

    return Diagnostic(file, line, char, severity, message)


def format_markdown_table(diagnostics: list[Diagnostic]) -> str:
    """Format list of diagnostics as a markdown table."""
    if not diagnostics:
        return "\nNo new errors found!"

    table = ["| File | Location | Message |", "|------|----------|---------|"]

    for diag in sorted(diagnostics, key=lambda x: (x.file, x.line, x.character)):
        # Escape pipe characters and replace newlines with HTML breaks
        message = diag.message.replace("|", "\\|").replace("\n", "<br>")
        location = f"L{diag.line}:{diag.character}"
        table.append(f"| {diag.file} | {location} | {message} |")

    return "\n".join(table)


def compare_pyright_outputs(base_file: str, new_file: str) -> None:
    """Compare two pyright JSON output files and display only new errors."""
    base_data = load_and_normalize_file(base_file)
    new_data = load_and_normalize_file(new_file)

    # Group diagnostics by file
    base_diags = set()
    new_diags = set()

    # Process diagnostics from type completeness symbols
    for data, diag_set in [(base_data, base_diags), (new_data, new_diags)]:
        for symbol in data.get("typeCompleteness", {}).get("symbols", []):
            for diag in symbol.get("diagnostics", []):
                if diag.get("severity", "") == "error":
                    diag_set.add(parse_diagnostic(diag))

    # Find new errors
    new_errors = list(new_diags - base_diags)

    print(format_markdown_table(new_errors))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python pyright_diff.py <base.json> <new.json>")
        sys.exit(1)

    compare_pyright_outputs(sys.argv[1], sys.argv[2])
