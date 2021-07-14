from setuptools import find_packages, setup

setup(
    name="prefect",
    version="2.0",
    install_requires=[
        "sqlalchemy >= 1.4, < 2.0",
        "xxhash >= 2.0, < 3.0",
        "pendulum >= 2.0, < 3.0",
        "pydantic >= 1.8, < 2.0",
    ],
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    include_package_data=True,
    python_requires=">=3.7",
)
