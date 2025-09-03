
from setuptools import setup, find_packages

setup(
    name="prefect-azuredevops",
    version="0.1.0",
    description="Prefect integration: Azure DevOps PAT credentials + repo helper",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "prefect>=3.3.5",
    ],
    python_requires=">=3.8",
)