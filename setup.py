from pathlib import Path

import versioneer
from setuptools import find_packages, setup


def read_requirements(file):
    requirements = []
    if Path(file).exists():
        requirements = open(file).read().strip().split("\n")
    return requirements


client_requires = read_requirements("requirements-client.txt")
install_requires = read_requirements("requirements.txt")[1:] + client_requires
dev_requires = read_requirements("requirements-dev.txt")
otel_requires = read_requirements("requirements-otel.txt")

setup(
    # Package metadata
    name="prefect",
    description="Workflow orchestration and management.",
    author="Prefect Technologies, Inc.",
    author_email="help@prefect.io",
    url="https://www.prefect.io",
    project_urls={
        "Changelog": "https://github.com/PrefectHQ/prefect/releases",
        "Documentation": "https://docs.prefect.io",
        "Source": "https://github.com/PrefectHQ/prefect",
        "Tracker": "https://github.com/PrefectHQ/prefect/issues",
    },
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    # Versioning
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    # Package setup
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    include_package_data=True,
    # CLI
    entry_points={
        "console_scripts": ["prefect=prefect.cli:app"],
        "mkdocs.plugins": [
            "render_swagger = prefect.utilities.render_swagger:SwaggerPlugin",
        ],
    },
    # Requirements
    python_requires=">=3.9",
    install_requires=install_requires,
    extras_require={
        "dev": dev_requires,
        "otel": otel_requires,
        # Infrastructure extras
        "aws": "prefect-aws>=0.5.0rc1",
        "azure": "prefect-azure>=0.4.0rc1",
        "gcp": "prefect-gcp>=0.6.0rc1",
        "docker": "prefect-docker>=0.6.0rc1",
        "kubernetes": "prefect-kubernetes>=0.4.0rc1",
        "shell": "prefect-shell>=0.3.0rc1",
        # Distributed task execution extras
        "dask": "prefect-dask>=0.3.0rc1",
        "ray": "prefect-ray>=0.4.0rc1",
        # Version control extras
        "bitbucket": "prefect-bitbucket>=0.3.0rc1",
        "github": "prefect-github>=0.3.0rc1",
        "gitlab": "prefect-gitlab>=0.3.0rc1",
        # Database extras
        "databricks": "prefect-databricks>=0.3.0rc1",
        "dbt": "prefect-dbt>=0.6.0rc1",
        "snowflake": "prefect-snowflake>=0.28.0rc1",
        "sqlalchemy": "prefect-sqlalchemy>=0.5.0rc1",
        "redis": "prefect-redis>=0.2.0",
        # Monitoring extras
        "email": "prefect-email>=0.4.0rc1",
        "slack": "prefect-slack>=0.3.0rc1",
    },
    classifiers=[
        "Natural Language :: English",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries",
    ],
)
