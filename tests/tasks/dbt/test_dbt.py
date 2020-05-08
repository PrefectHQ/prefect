import os
import pathlib
import sys

import pytest

from prefect import Flow
from prefect.tasks.dbt import DbtShellTask


pytestmark = pytest.mark.skipif(
    sys.platform == "win32", reason="DbtShellTask currently not supported on Windows"
)


@pytest.fixture()
def test_path():
    return os.path.dirname(os.path.realpath(__file__))


def test_shell_creates_profiles_yml_file(test_path):
    with Flow(name="test") as f:
        task = DbtShellTask(
            profile_name="default",
            environment="test",
            dbt_kwargs={
                "type": "snowflake",
                "threads": 1,
                "account": "JH72176.us-east-1",
                "user": "jane@company.com",
                "role": "analyst",
                "database": "staging",
                "warehouse": "data_science",
                "schema": "analysis",
                "private_key_path": "/src/private_key.p8",
                "private_key_passphrase": "password123",
            },
            overwrite_profiles=True,
            profiles_dir=test_path,
        )(command="ls")

    out = f.run()
    profiles_path = os.path.join(test_path, "profiles.yml")
    assert out.is_successful()
    assert os.path.exists(profiles_path)
    os.remove(profiles_path)


def test_shell_uses_dbt_envar(test_path):
    dbt_project_path = os.path.join(test_path, "dbt_project")
    os.environ["DBT_PROFILES_DIR"] = dbt_project_path
    pathlib.Path(dbt_project_path).mkdir(parents=True, exist_ok=True)
    real_profiles_path = os.path.join(dbt_project_path, "profiles.yml")
    open(real_profiles_path, "a").close()

    with Flow(name="test") as f:
        task = DbtShellTask(
            profile_name="default",
            environment="test",
            dbt_kwargs={
                "type": "snowflake",
                "threads": 1,
                "account": "JH72176.us-east-1",
                "user": "jane@company.com",
                "role": "analyst",
                "database": "staging",
                "warehouse": "data_science",
                "schema": "analysis",
                "private_key_path": "/src/private_key.p8",
                "private_key_passphrase": "password123",
            },
            overwrite_profiles=False,
            profiles_dir=test_path,
        )(command="ls")

    out = f.run()
    missing_profiles_path = os.path.join(test_path, "profiles.yml")
    assert out.is_successful()
    assert not os.path.exists(missing_profiles_path)
    os.remove(real_profiles_path)
    pathlib.Path(dbt_project_path).rmdir()
