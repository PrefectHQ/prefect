import sys

from setuptools import find_packages, setup

import versioneer

## base requirements
install_requires = open("requirements.txt").read().strip().split("\n")
dev_requires = open("dev-requirements.txt").read().strip().split("\n")

extras = {
    "airtable": ["airtable-python-wrapper >= 0.11, < 0.12"],
    "aws": ["boto3 >= 1.9, < 2.0"],
    "dev": dev_requires,
    "google": [
        "google-cloud-bigquery >= 1.6.0, < 2.0",
        "google-cloud-storage >= 1.13, < 2.0",
    ],
    "kubernetes": ["dask-kubernetes == 0.7.0", "kubernetes >= 8.0.1, < 9.0"],
    "templates": ["jinja2 >= 2.0, < 3.0"],
    "viz": ["graphviz >= 0.8.3"],
    "twitter": ["tweepy >= 3.5, < 4.0"],
}

if sys.version_info < (3, 6):
    extras["dev"].remove("black")

extras["all_extras"] = sum(extras.values(), [])


setup(
    name="prefect",
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    install_requires=install_requires,
    extras_require=extras,
    scripts=[],
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    include_package_data=True,
    entry_points={"console_scripts": ["prefect=prefect.cli:cli"]},
    python_requires=">=3.5",
    description="The Prefect Core automation and scheduling engine.",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://www.github.com/PrefectHQ/prefect",
    license="Apache License 2.0",
    author="Prefect Technologies, Inc.",
    author_email="help@prefect.io",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Topic :: Software Development :: Libraries",
        "Topic :: System :: Monitoring",
    ],
)
