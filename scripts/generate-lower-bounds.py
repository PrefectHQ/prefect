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


def generate_lower_bounds(input_file):
    for line in input_file:
        output_line = ""

        # Split the package from the conditional section
        pkg, _, cond = line.partition(";")
        # Parse the package name and the
        pkg_parsed = re.match(
            r"^([\w\d_\-\[\]]*)\s*.*\s*(?:>=|==|~=)\s*([\d*\.?]+)", pkg
        )

        if not pkg_parsed:
            # There is no versioning for this requirement
            output_line += pkg.strip()
        else:
            # Pin to the lowest version
            pkg_name, pkg_min_version = (
                pkg_parsed.groups()[0].strip(),
                pkg_parsed.groups()[1].strip(),
            )
            output_line += f"{pkg_name}=={pkg_min_version}"

        # Include the condition if it exists
        if cond:
            output_line += f"; {cond.strip()}"

        yield output_line


if __name__ == "__main__":
    input_path = sys.argv[1] if len(sys.argv) > 1 else "requirements.txt"
    with open(input_path, "r") as input_file:
        for line in generate_lower_bounds(input_file):
            print(line)
