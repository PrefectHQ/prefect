#!/usr/bin/env python3
"""
This helper script compiles all of our lower version bounds on all base dependencies
from our `requirements.txt` file into a new file which is printed to stdout.  In this
new requirements file all dependencies are pinned to their lowest allowed versions.
We use this new requirements file to test that we still support all of our
specified versions.

Usage:

    generate-lower-bounds.py [<input-path>]

The input path defaults to `requirements.txt` but can be customized:

    generate-lower-bounds.py requirements-dev.txt

A file can be generated and used with pip:

    generate-lower-bounds.py > requirements-lower.txt
    pip install -r requirements-lower.txt

NOTE: Writing requirements to the same file that they are read from will result in an
      empty file.

It can be used inline with pip if newlines are converted to spaces:

   pip install $(generate-lower-bounds.py | tr "\n" " ")

"""

import re
import sys

LOWER_BOUND_RE = re.compile(
    r"""
    ^([\w\d_\-\[\]]+)   # Capture the name of the package at start of string
    .*                  # Ignore any non-lower bound version specifications
    (?:>=|==|~=)        # Begin parsing a version with a lower bound like equality
    \s*                 # Allow arbitrary whitespace between the equality and version
    (
        [\d*\.?]+       # Capture versions of arbitrary length X.Y.Z...
        (\w+\d*)?      # Capture following alpha/beta/rc designations
    )
    """,
    re.VERBOSE,
)


def generate_lower_bounds(input_file):
    for line in input_file:
        output_line = ""

        # Split the package name and versions from the conditional section
        requirement_package, _, requirement_condition = line.partition(";")

        # Parse the package name and lower bound
        lower_bound_match = LOWER_BOUND_RE.match(requirement_package)

        if not lower_bound_match:
            # There is no versioning for this requirement, just include it as-is
            output_line += requirement_package.strip()
        else:
            capture_groups = lower_bound_match.groups()

            # Pin to the lowest version
            package_name, lower_bound_version = (
                capture_groups[0].strip(),
                capture_groups[1].strip(),
            )
            output_line += f"{package_name}=={lower_bound_version}"

        # Include the condition unaltered
        if requirement_condition:
            output_line += f"; {requirement_condition.strip()}"

        yield output_line


if __name__ == "__main__":
    input_path = sys.argv[1] if len(sys.argv) > 1 else "requirements.txt"
    with open(input_path, "r") as input_file:
        for line in generate_lower_bounds(input_file):
            print(line)
