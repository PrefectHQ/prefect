"""
This helper script compiles all of our lower version bounds
on all base dependencies from our `requirements.txt` file into a new
`lower_requirements.txt` file.  In this new requirements file all dependencies
are pinned to their lowest allowed versions.  We use this
new requirements file to test that we still support all of our
specified versions.
"""
import re


with open("requirements.txt", "r") as f:
    reqs = f.readlines()


with open("lower_requirements.txt", "w") as g:
    for req in reqs:
        pkg_data = re.split(">=|,", req.replace("~", ">"))
        g.write(pkg_data[0].strip() + " == " + pkg_data[1].strip() + "\n")
