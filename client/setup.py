import tomli
from setuptools import find_packages, setup

from prefect import __version__ as PREFECT_CORE_VERSION


def get_optional_requires(extra):
    with open("pyproject.toml", "rb") as f:
        pyproject_data = tomli.load(f)  # noqa

    client_requires = (
        pyproject_data.get("project", {})
        .get("optional-dependencies", {})
        .get(extra, {})
    )
    return client_requires


install_requires = get_optional_requires("client")

# grab and use the first three version digits (the generated tag)
client_version = ".".join(PREFECT_CORE_VERSION.split(".")[:3])

setup(
    # Package metadata
    name="prefect-client",
    description="Workflow orchestration and management.",
    author="Prefect Technologies, Inc.",
    author_email="help@prefect.io",
    url="https://www.prefect.io",
    project_urls={
        "Changelog": "https://github.com/PrefectHQ/prefect/blob/main/RELEASE-NOTES.md",
        "Documentation": "https://docs.prefect.io",
        "Source": "https://github.com/PrefectHQ/prefect",
        "Tracker": "https://github.com/PrefectHQ/prefect/issues",
    },
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    # Versioning
    version=client_version,
    # Package setup
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    include_package_data=True,
    # Requirements
    python_requires=">=3.8",
    install_requires=install_requires,
    extras_require={"notifications": ["apprise>=1.1.0, <2.0.0"]},
    classifiers=[
        "Natural Language :: English",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries",
    ],
)
