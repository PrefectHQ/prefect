# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license

import sys

from setuptools import find_packages, setup

import versioneer

install_requires = [
    "prefect >= 0.6",
    "ariadne >= 0.8.0, < 0.11.0",
    "alembic >= 1.0, < 2.0",
    "asyncpg >= 0.19, < 0.21",
    "black",
    # cython can be used to speed up pydantic
    "cython >= 0.29, < 0.30",
    "click >= 6.7, <8.0",
    "coolname >= 1.1, < 2.0",
    "cryptography >= 2.2, < 3.0",
    "docker >= 3.4,< 5.0",
    "graphql-core < 3.1",
    "gunicorn >= 19.9,< 20.1",
    "httpx >= 0.9.6, < 0.11.0",
    "pendulum >= 2.0, < 3.0",
    "psycopg2-binary >= 2.7, < 3.0",
    "pydantic >= 1.2, < 2.0",
    "pyjwt >= 1.6, < 2.0",
    "python-box >= 3.4, < 5.0",
    "python-slugify >= 1.2,< 5.0",
    "starlette >= 0.13, < 0.14",
    "toml >= 0.9.0, < 0.11",
    "ujson >= 1.35, < 3.0",
    # "uvicorn >= 0.11.0, < 0.12.0",
    # temporary work around until PR is merged https://github.com/encode/uvicorn/pull/566
    "uvicorn @ git+https://github.com/encode/uvicorn.git@c4900d19e1100a7b1a93a99f3d3ec6b717ffea41#egg=uvicorn",
    "pyyaml >= 3.13, < 6.0",
    # Tests & Development
    # include ipython for ease of debugging async functions
    "asynctest >= 0.13, < 0.14",
    "pytest >= 5.0, < 6.0",
    "pytest-asyncio",
    "pytest-cov",
    "pytest-env",
    "pytest-xdist",
]


setup(
    name="prefect_server",
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    description="",
    long_description="",
    url="https://github.com/PrefectHQ/prefect",
    author="Prefect Technologies, Inc.",
    author_email="hello@prefect.io",
    install_requires=install_requires,
    extras_require={},
    scripts=[],
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    include_package_data=True,
    entry_points="""
        [console_scripts]
        prefect-server=prefect_server.cli:cli
        """,
)
