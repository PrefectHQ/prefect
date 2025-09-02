from setuptools import setup, find_packages

with open("README.md") as readme_file:
    readme = readme_file.read()

setup(
    name="prefect-azure-devops",
    version="0.1.0",
    description="Prefect integrations for working with Azure DevOps repositories",
    long_description=readme,
    long_description_content_type="text/markdown",
    author="Prefect Community",
    author_email="community@prefect.io",
    keywords="prefect azure devops git repository",
    url="https://github.com/PrefectHQ/prefect-azure-devops",
    packages=find_packages(exclude=("tests",)),
    python_requires=">=3.8",
    install_requires=[
        "prefect>=2.0.0,<3.0.0",
        "pydantic",
    ],
    extras_require={
        "dev": [
            "pytest",
            "pytest-asyncio",
            "pytest-mock",
            "black",
            "ruff", 
            "mypy",
            "pre-commit",
        ]
    },
    entry_points={
        "prefect.collections": [
            "prefect_azure_devops = prefect_azure_devops",
        ]
    },
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
