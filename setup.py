import versioneer
from setuptools import find_packages, setup


install_requires = open("requirements.txt").read().strip().split("\n")
dev_requires = open("requirements-dev.txt").read().strip().split("\n")


setup(
    # Package metadata
    name="prefect",
    version=versioneer.get_version(),
    description="Workflow orchestration and management.",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
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
    python_requires=">=3.7",
    install_requires=install_requires,
    extras_require={"dev": dev_requires},
)
