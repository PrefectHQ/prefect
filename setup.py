import sys
import os

from setuptools import find_packages, setup
from setuptools.command.install import install

import versioneer


class VerifyVersionCommand(install):
    """Verify that the git tag matches our package version"""

    description = "verify that the git tag matches our package version"

    def run(self):
        version = versioneer.get_version()
        tag = os.getenv("CIRCLE_TAG")

        if tag != version:
            info = "Failed version verification: '{0}' does not match the version of this app: '{1}'".format(
                tag, version
            )
            sys.exit(info)


## base requirements
install_requires = open("requirements.txt").read().strip().split("\n")
dev_requires = open("dev-requirements.txt").read().strip().split("\n")
test_requires = open("test-requirements.txt").read().strip().split("\n")

orchestration_extras = {
    "aws": ["boto3 >= 1.9, < 2.0"],
    "azure": ["azure-storage-blob >= 12.1.0, < 13.0"],
    "bitbucket": ["atlassian-python-api >= 2.0.1"],
    "gcp": [
        "google-cloud-secret-manager >= 2.4.0",
        "google-cloud-storage >= 1.13, < 2.0",
    ],
    "git": ["dulwich >= 0.19.7"],
    "github": ["PyGithub >= 1.51, < 2.0"],
    "gitlab": ["python-gitlab >= 2.5.0, < 3.0"],
    "kubernetes": ["kubernetes >= 9.0.0a1, <= 13.0"],
}

extras = {
    "airtable": ["airtable-python-wrapper >= 0.11, < 0.12"],
    "aws": orchestration_extras["aws"],
    "azure": [
        "azure-storage-blob >= 12.1.0, < 13.0",
        "azureml-sdk >= 1.0.65, < 1.1",
        "azure-cosmos >= 3.1.1, <3.2",
    ],
    "bitbucket": orchestration_extras["bitbucket"],
    "dask_cloudprovider": ["dask_cloudprovider[aws] >= 0.2.0"],
    "dev": dev_requires + test_requires,
    "dropbox": ["dropbox ~= 9.0"],
    "ge": ["great_expectations >= 0.11.1"],
    "gcp": [
        "google-cloud-bigquery >= 1.6.0, < 2.0",
    ]
    + orchestration_extras["gcp"],
    "git": orchestration_extras["git"],
    "github": orchestration_extras["github"],
    "gitlab": orchestration_extras["gitlab"],
    "google": [
        "google-cloud-bigquery >= 1.6.0, < 2.0",
    ]
    + orchestration_extras["gcp"],
    "gsheets": ["gspread >= 3.6.0"],
    "jira": ["jira >= 2.0.0"],
    "jupyter": ["papermill >= 2.2.0", "nbconvert >= 6.0.7"],
    "kafka": ["confluent-kafka >= 1.7.0"],
    "kubernetes": ["dask-kubernetes >= 0.8.0"] + orchestration_extras["kubernetes"],
    "pandas": ["pandas >= 1.0.1"],
    "postgres": ["psycopg2-binary >= 2.8.2"],
    "mysql": ["pymysql >= 0.9.3"],
    "sql_server": ["pyodbc >= 4.0.30"],
    "pushbullet": ["pushbullet.py >= 0.11.0"],
    "redis": ["redis >= 3.2.1"],
    "rss": ["feedparser >= 5.0.1, < 6.0"],
    "snowflake": ["snowflake-connector-python >= 1.8.2, < 2.5"],
    "spacy": ["spacy >= 2.0.0, < 3.0.0"],
    "templates": ["jinja2 >= 2.0, < 3.0"],
    "test": test_requires,
    "viz": ["graphviz >= 0.8.3"],
    "twitter": ["tweepy >= 3.5, < 4.0"],
    "dremio": ["pyarrow>=0.15.1"],
    "exasol": ["pyexasol >= 0.16.1"],
    "sodasql": ["soda-sql >= 2.0.0b25"],
    "sendgrid": ["sendgrid >= 6.7.0"],
}


if sys.version_info < (3, 6):
    extras["dev"].remove("black")

extras["all_extras"] = sum(extras.values(), [])

# Extras for docker image builds to include for orchestration
extras["all_orchestration_extras"] = sum(orchestration_extras.values(), [])

# CI extras to control dependencies for tests
extras["task_library_ci"] = sum(extras.values(), [])
extras["task_library_ci"] = [
    r
    for r in extras["task_library_ci"]
    if not r.startswith("dask_cloudprovider") and not r.startswith("pyodbc")
]

extras["base_library_ci"] = (
    extras["all_orchestration_extras"]
    + extras["dev"]
    + extras["pandas"]
    + extras["jira"]
)

cmdclass = {
    "verify_version": VerifyVersionCommand,
}
cmdclass.update(versioneer.get_cmdclass())

setup(
    name="prefect",
    version=versioneer.get_version(),
    cmdclass=cmdclass,
    install_requires=install_requires,
    extras_require=extras,
    scripts=[],
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    package_data={"prefect": ["py.typed"]},
    include_package_data=True,
    entry_points={"console_scripts": ["prefect=prefect.cli:cli"]},
    python_requires=">=3.6",
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
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Topic :: Software Development :: Libraries",
        "Topic :: System :: Monitoring",
    ],
)
