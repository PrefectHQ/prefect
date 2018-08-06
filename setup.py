from setuptools import find_packages, setup

import versioneer

install_requires = [
    "click >= 6.7, < 7.0",
    "cloudpickle >= 0.5.3, < 0.6.0",
    "croniter >= 0.3.23, < 0.4",
    "cryptography >= 2.2.2, < 3.0",
    "dask >= 0.18, < 0.19",
    "distributed >= 1.21.8, < 2.0",
    "docker >= 3.4.1, < 3.5",
    "graphviz >= 0.8.3, < 0.9",
    "jsonpickle >= 0.9.6, < 1.0",
    "mypy_extensions >= 0.3.0, < 0.4",
    "python-dateutil >= 2.7.3, < 3.0",
    "requests >= 2.19.1, < 3.0",
    "toml >= 0.9.4, < 1.0",
    "typing >= 3.6.4, < 4.0",
    "typing_extensions >= 3.6.4, < 4.0",
]

extras = {"dev": ["pytest", "pytest-env", "pytest-xdist"]}

setup(
    name="prefect",
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    description="",
    long_description=open("README.md").read(),
    url="https://www.github.com/prefecthq/prefect",
    author="Jeremiah Lowin",
    author_email="jeremiah@prefect.io",
    install_requires=install_requires,
    extras_require=extras,
    scripts=[],
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    include_package_data=True,
    entry_points={"console_scripts": ["prefect=prefect.cli:cli"]},
)
