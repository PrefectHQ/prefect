from setuptools import find_packages, setup

install_requires = [
    "click",
    # 'cloudpickle > 0.3.1',  # support for pickling loggers was added after 0.3.1
    "croniter",
    "cryptography",
    # 'distributed >= 1.16.1',
    "jsonpickle",
    "mypy_extensions",
    "python-dateutil",
    "requests",
    "wrapt",
    "toml",
    "typing",
    "typing_extensions",
    # "xxhash",
]

extras = {
    # 's3': ['awsfs'],
    # 'gcs': ['https://github.com/martindurant/gcsfs.git'],
    "dev": ["pytest", "pytest-env", "pytest-xdist", "pre-commit"]
}

setup(
    name="prefect",
    # corresponds to __version__
    version="0.2",
    description="",
    long_description=open("README.md").read(),
    url="https://gitlab.com/prefect/prefect",
    author="Jeremiah Lowin",
    author_email="jlowin@prefect.io",
    install_requires=install_requires,
    extras_require=extras,
    scripts=[],
    packages=find_packages(),
    include_package_data=True,
    entry_points={"console_scripts": ["prefect=prefect.cli:cli"]},
)
