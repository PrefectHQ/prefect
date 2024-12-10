#!/usr/bin/env python3

import argparse
import json
import re
import subprocess
import sys
from argparse import Namespace
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Set


@dataclass
class Diagnostic:
    file: str
    severity: str
    message: str
    line: int


@dataclass
class Symbol:
    category: str
    name: str
    diagnostics: List[Diagnostic]


class DiffChange(NamedTuple):
    file: Path
    line: int


class TypeAnalyzer:
    def __init__(self, target_branch: str = "main", regenerate: bool = False) -> None:
        self.target_branch: str = target_branch
        self.regenerate: bool = regenerate
        self.analysis_file: Path = Path("prefect-analysis.json")

    def generate_analysis(self) -> None:
        """Generate fresh type analysis using pyright."""
        print("Generating type analysis...")
        try:
            result: subprocess.CompletedProcess[str] = subprocess.run(
                [
                    "uv",
                    "tool",
                    "run",
                    "--with-editable",
                    ".",
                    "pyright",
                    "--verifytypes",
                    "prefect",
                    "--ignoreexternal",
                    "--outputjson",
                ],
                capture_output=True,
                text=True,
            )

            if result.stdout:
                self.analysis_file.write_text(result.stdout)
                print("Analysis file generated")
            else:
                print("Warning: Analysis generation produced no output")
                if result.stderr:
                    print(f"stderr: {result.stderr}")
                sys.exit(1)

        except subprocess.SubprocessError as e:
            print(f"Error running analysis command: {e}")
            sys.exit(1)

    def parse_analysis(self) -> List[Symbol]:
        """Parse the analysis JSON file and return only symbols with diagnostics."""
        try:
            data: Dict = json.loads(self.analysis_file.read_text())
            symbols: List[Symbol] = []

            for symbol_data in data["typeCompleteness"]["symbols"]:
                if not symbol_data.get("diagnostics"):
                    continue

                diagnostics: List[Diagnostic] = []
                for diag in symbol_data["diagnostics"]:
                    if not (
                        diag.get("file")
                        and diag.get("range", {}).get("start", {}).get("line")
                    ):
                        continue

                    diagnostics.append(
                        Diagnostic(
                            file=diag["file"],
                            severity=diag.get("severity", ""),
                            message=diag["message"],
                            line=diag["range"]["start"]["line"],
                        )
                    )

                if diagnostics:
                    symbols.append(
                        Symbol(
                            category=symbol_data["category"],
                            name=symbol_data["name"],
                            diagnostics=diagnostics,
                        )
                    )

            return symbols
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Error parsing analysis file: {e}")
            return []

    def parse_diff_line(
        self, line: str, current_file: Optional[Path], current_line: int
    ) -> tuple[Optional[Path], int, Optional[DiffChange]]:
        """Parse a single line from the git diff output."""
        change: Optional[DiffChange] = None

        if line.startswith("+++"):
            # New file
            file_path = line[4:].strip()
            if file_path.startswith("b/"):
                file_path = file_path[2:]
            current_file = Path(file_path)
            current_line = 0
        elif line.startswith("@@"):
            # Parse the hunk header to get the starting line number
            match = re.search(r"\+(\d+)", line)
            if match:
                current_line = int(match.group(1))
        elif current_file and line.startswith("+"):
            # This is a changed/added line
            change = DiffChange(current_file, current_line)
            current_line += 1

        return current_file, current_line, change

    def get_changed_lines(self) -> List[DiffChange]:
        """Get list of changed files and specific lines."""
        changes: List[DiffChange] = []
        try:
            # Get the diff with line numbers
            diff: str = subprocess.run(
                ["git", "diff", "-U0", self.target_branch],
                capture_output=True,
                text=True,
                check=True,
            ).stdout

            current_file: Optional[Path] = None
            current_line: int = 0

            for line in diff.splitlines():
                current_file, current_line, change = self.parse_diff_line(
                    line, current_file, current_line
                )
                if change:
                    changes.append(change)

            return changes

        except subprocess.CalledProcessError as e:
            print(f"Error getting changed lines: {e}")
            return []

    def get_matching_diagnostics(
        self, diagnostic: Diagnostic, changed_lines: Set[tuple[Path, int]]
    ) -> bool:
        """Check if a diagnostic matches any changed lines."""
        diag_path: Path = Path(diagnostic.file)
        return any(
            diag_path.name == change_file.name and diagnostic.line == change_line
            for change_file, change_line in changed_lines
        )

    def print_analysis(self, symbols: List[Symbol], changes: List[DiffChange]) -> None:
        """Print only diagnostics that match changed files and lines."""
        issues_found: bool = False

        # Create a set of (file, line) tuples for quick lookup
        changed_lines: Set[tuple[Path, int]] = {(c.file, c.line) for c in changes}

        for symbol in symbols:
            matching_diagnostics: List[Diagnostic] = [
                diagnostic
                for diagnostic in symbol.diagnostics
                if self.get_matching_diagnostics(diagnostic, changed_lines)
            ]

            if matching_diagnostics:
                issues_found = True
                print(f"\nSymbol: {symbol.name}")
                print(f"Category: {symbol.category}")
                print("Issues:")
                for diag in matching_diagnostics:
                    print(f"  Line {diag.line}: {diag.message}")
                    print(f"  File: {diag.file}")
                print("---")

        if not issues_found:
            print("\nNo type issues found in changed lines.")

    def run(self) -> None:
        """Run the complete analysis."""
        if self.regenerate or not self.analysis_file.exists():
            self.generate_analysis()

        changes: List[DiffChange] = self.get_changed_lines()
        if not changes:
            print(f"No changes detected compared to {self.target_branch}")
            return

        symbols: List[Symbol] = self.parse_analysis()
        if not symbols:
            print("No type issues found")
            return

        self.print_analysis(symbols, changes)


def parse_args() -> Namespace:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Analyze type issues in changed files"
    )
    parser.add_argument(
        "--branch",
        default="main",
        help="Target branch to compare against (default: main)",
    )
    parser.add_argument(
        "--regenerate", action="store_true", help="Force regeneration of analysis file"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    analyzer = TypeAnalyzer(target_branch=args.branch, regenerate=args.regenerate)
    analyzer.run()
