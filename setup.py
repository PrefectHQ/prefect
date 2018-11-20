# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

from setuptools import find_packages, setup

import configparser
import sys
import versioneer

config = configparser.ConfigParser()
config.read("requirements.ini")

## base requirements
install_requires = ["".join(req) for req in config["base"].items()]

## section dependencies
includes = {}
for section in config.sections():
    includes[section] = config[section].pop("include", "").split(",")

extras = {
    "dev": ["".join(req) for req in config["dev"].items()],
    "viz": ["".join(req) for req in config["viz"].items()],
    "templates": ["".join(req) for req in config["templates"].items()],
}

## process include keyword for related sections
for section in extras:
    for other in includes[section]:
        extras[section] += extras.get(other.strip(), [])


if sys.version_info >= (3, 6):
    extras["dev"] += ["black"]

extras["all_extras"] = extras["dev"] + extras["viz"] + extras["templates"]


setup(
    name="prefect",
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    description="",
    long_description=open("README.md").read(),
    url="https://www.github.com/prefecthq/prefect",
    author="Prefect Technologies, Inc.",
    author_email="help@prefect.io",
    install_requires=install_requires,
    extras_require=extras,
    scripts=[],
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    include_package_data=True,
    entry_points={"console_scripts": ["prefect=prefect.cli:cli"]},
)
