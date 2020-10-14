import os
import sys

import pytest

from prefect import Flow
from prefect.tasks.dbt import DbtShellTask


pytestmark = pytest.mark.skipif(
    sys.platform == "win32", reason="DbtShellTask currently not supported on Windows"
)


def test_shell_result_from_stdout(tmpdir):
    dbt_dir = tmpdir.mkdir("dbt")

    task = DbtShellTask(
        command="dbt --version",
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
        profiles_dir=str(dbt_dir),
    )
    out = task.run()
    # default config should return a string
    assert isinstance(out, str)
    # check that the result is not empty
    assert len(out) > 0


def test_shell_result_from_stdout_with_full_return(tmpdir):
    dbt_dir = tmpdir.mkdir("dbt")

    task = DbtShellTask(
        return_all=True,
        command="dbt --version",
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
        profiles_dir=str(dbt_dir),
    )
    out = task.run()
    # when set to `return_all=True`, should return a list
    assert isinstance(out, list)
    # check that the result is multiple lines
    assert len(out) > 1


def test_shell_creates_profiles_yml_file(tmpdir):
    dbt_dir = tmpdir.mkdir("dbt")
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
            profiles_dir=str(dbt_dir),
        )(command="ls")

    out = f.run()
    profiles_path = dbt_dir.join("profiles.yml")
    assert out.is_successful()
    assert os.path.exists(profiles_path)


def test_shell_uses_dbt_envar(tmpdir, monkeypatch):
    dbt_project_path = tmpdir.mkdir("dbt_project")
    monkeypatch.setenv("DBT_PROFILES_DIR", str(dbt_project_path))
    real_profiles_path = dbt_project_path.join("profiles.yml")
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
            profiles_dir=str(tmpdir),
        )(command="ls")

    out = f.run()
    missing_profiles_path = tmpdir.join("profiles.yml")
    assert out.is_successful()
    assert not os.path.exists(missing_profiles_path)


def test_task_creates_default_profile_if_none_exists():
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
        )(command="ls")
    out = f.run()
    default_profiles_path = os.path.exists(
        os.path.join(os.path.expanduser("~"), ".dbt")
    )
    assert out.is_successful()
    assert default_profiles_path
