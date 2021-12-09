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

It can be used inline with pip if newlines are converted to spaces:

   pip install $(generate-lower-bounds.py | tr "\n" " ")
   
"""
import re
import sys


def generate_lower_bounds(input_path):
    with open(input_path, "r") as f:
        for req in f:
            pkg_data = re.split(">=|,|==", req.replace("~", ">"))

            if len(pkg_data) == 1:
                # There is no versioning for this requirement
                print(pkg_data[0].strip())
            else:
                print(pkg_data[0].strip() + "==" + pkg_data[1].strip())


if __name__ == "__main__":
    input_path = sys.argv[1] if len(sys.argv) > 1 else "requirements.txt"
    generate_lower_bounds(input_path)
