"""
Script to generate API reference documentation using mdxify.
"""

import subprocess
import sys


def main() -> None:
    """Generate API reference documentation."""
    cmd = [
        "uvx",
        "--with-editable",
        ".",
        "mdxify@latest",
        "--all",
        "--root-module",
        "prefect",
        "--output-dir",
        "docs/v3/api-ref/python",
        "--anchor-name",
        "Python SDK Reference",
        "--exclude",
        "prefect.agent",
        "--include-inheritance",
        "--repo-url",
        "https://github.com/PrefectHQ/prefect",
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"Error generating API reference: {result.stderr}", file=sys.stderr)
        sys.exit(result.returncode)

    print(result.stdout)


if __name__ == "__main__":
    main()
