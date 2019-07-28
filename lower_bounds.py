import re


with open("requirements.txt", "r") as f:
    reqs = f.readlines()


with open("lower_requirements.txt", "w") as g:
    for req in reqs:
        pkg_data = re.split(">=|,", req.replace("~", ">"))
        g.write(pkg_data[0].strip() + " == " + pkg_data[1].strip() + "\n")
