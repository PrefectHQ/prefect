import versioneer
from setuptools import find_packages, setup

install_requires = [
    "click",
    # 'cloudpickle > 0.3.1',  # support for pickling loggers was added after 0.3.1
    "croniter",
    "cryptography",
    "distributed >= 1.16.1",
    "graphviz",
    "jsonpickle",
    "mypy_extensions",
    "python-dateutil",
    "requests",
    "wrapt",
    "toml",
    "typing",
    "typing_extensions",
]

extras = {"dev": ["pytest", "pytest-env", "pytest-xdist"]}

setup(
    name="prefect",
    # corresponds to __version__
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
    packages=find_packages(),
    include_package_data=True,
    entry_points={"console_scripts": ["prefect=prefect.cli:cli"]},
)
