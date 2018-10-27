# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

from setuptools import find_packages, setup

import sys
import versioneer

install_requires = [
    "click >= 6.7, < 7.0",
    "cloudpickle == 0.5.3",
    "croniter >= 0.3.23, < 0.4",
    "cryptography >= 2.2.2, < 3.0",
    "dask >= 0.18, < 0.19",
    "distributed >= 1.21.8, < 2.0",
    "docker >= 3.4.1, < 3.5",
    "mypy_extensions >= 0.3.0, < 0.4",
    "python-dateutil >= 2.7.3, < 3.0",
    "requests >= 2.19.1, < 3.0",
    "toml >= 0.9.4, < 1.0",
    "typing >= 3.6.4, < 4.0",
    "typing_extensions >= 3.6.4, < 4.0",
    "xxhash >= 1.2.0, < 2.0",
]

templates = ["jinja2 >= 2.0, < 3.0"]
viz = ["bokeh == 0.13.0", "graphviz >= 0.8.3"]
dev = [
    "pre-commit",
    "pytest >= 3.8, < 4.0",
    "pytest-cov",
    "pytest-env",
    "pytest-xdist",
    "Pygments == 2.2.0",
]

if sys.version_info >= (3, 6):
    dev += ["black"]

extras = {
    "dev": dev + viz,
    "viz": viz,
    "templates": templates,
    "all_extras": dev + templates + viz,
}

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
