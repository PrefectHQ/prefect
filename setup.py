from setuptools import setup, find_packages

install_requires = open("requirements.txt").read().strip().split("\n")
dev_requires = open("requirements-dev.txt").read().strip().split("\n")

setup(
    name="prefect_orion",
    version="0.0.1",
    # Package loading
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    # Requirements
    python_requires=">=3.7",
    install_requires=install_requires,
    extras_require={"dev": dev_requires},
)
