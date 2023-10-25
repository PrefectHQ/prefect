import versioneer
from setuptools import find_packages, setup

install_requires = open("requirements-client.txt").read().strip().split("\n")

# grab and use the first three version digits (the generated tag)
_version = versioneer.get_version().split(".")
client_version = ".".join(_version[:3]).split("+")[0]

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
        "Topic :: Software Development :: Libraries",
    ],
)
