# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

import sys

from setuptools import find_packages, setup

import versioneer

## base requirements
install_requires = open("requirements.txt").read().strip().split("\n")
dev_requires = open("dev-requirements.txt").read().strip().split("\n")

extras = {
    "dev": dev_requires,
    "viz": ["graphviz >= 0.8.3"],
    "templates": ["jinja2 >= 2.0, < 3.0"],
}

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
