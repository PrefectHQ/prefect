import os
import sys

from requests_mock import Mocker
import pytest

from prefect import Flow
from prefect.engine.signals import FAIL
from prefect.tasks.dbt import DbtShellTask, DbtCloudRunJob

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


def test_dbt_cloud_run_job_create_task_without_cause():
    dbt_run_job_task = DbtCloudRunJob(account_id=1234, token="xyz", job_id=1234)

    assert dbt_run_job_task.account_id == 1234
    assert dbt_run_job_task.token == "xyz"
    assert dbt_run_job_task.job_id == 1234
    assert dbt_run_job_task.cause is None


def test_dbt_cloud_run_job_create_task_with_cause():
    dbt_run_job_task = DbtCloudRunJob(
        account_id=1234, token="xyz", job_id=1234, cause="foo"
    )

    assert dbt_run_job_task.account_id == 1234
    assert dbt_run_job_task.token == "xyz"
    assert dbt_run_job_task.job_id == 1234
    assert dbt_run_job_task.cause == "foo"


def test_dbt_cloud_run_job_create_task_from_default_env_vars(monkeypatch):
    monkeypatch.setenv("DBT_CLOUD_ACCOUNT_ID", str(1234))
    monkeypatch.setenv("DBT_CLOUD_JOB_ID", str(1234))
    monkeypatch.setenv("DBT_CLOUD_TOKEN", "xyz")
    dbt_run_job_task = DbtCloudRunJob()

    assert dbt_run_job_task.account_id == 1234
    assert dbt_run_job_task.token == "xyz"
    assert dbt_run_job_task.job_id == 1234
    assert dbt_run_job_task.cause is None


def test_dbt_cloud_run_job_create_task_from_env_vars(monkeypatch):
    monkeypatch.setenv("ACCOUNT_ID", str(1234))
    monkeypatch.setenv("JOB_ID", str(1234))
    monkeypatch.setenv("TOKEN", "xyz")
    dbt_run_job_task = DbtCloudRunJob(
        account_id_env_var_name="ACCOUNT_ID",
        job_id_env_var_name="JOB_ID",
        token_env_var_name="TOKEN",
    )

    assert dbt_run_job_task.account_id == 1234
    assert dbt_run_job_task.token == "xyz"
    assert dbt_run_job_task.job_id == 1234
    assert dbt_run_job_task.cause is None


def test_dbt_cloud_run_job_raises_value_error_with_missing_cause():
    run_job = DbtCloudRunJob()
    with pytest.raises(ValueError) as exc:
        run_job.run()
    assert "Cause cannot be None." in str(exc)


def test_dbt_cloud_run_job_raises_value_error_with_missing_account_id():
    run_job = DbtCloudRunJob()
    with pytest.raises(ValueError) as exc:
        run_job.run(cause="foo")
    assert "dbt Cloud Account ID cannot be None." in str(exc)


def test_dbt_cloud_run_job_raises_value_error_with_missing_job_id():
    run_job = DbtCloudRunJob()
    with pytest.raises(ValueError) as exc:
        run_job.run(cause="foo", account_id=1234)
    assert "dbt Cloud Job ID cannot be None." in str(exc)


def test_dbt_cloud_run_job_raises_value_error_with_missing_token():
    run_job = DbtCloudRunJob()
    with pytest.raises(ValueError) as exc:
        run_job.run(cause="foo", account_id=1234, job_id=1234)
    assert "token cannot be None." in str(exc)


def test_dbt_cloud_run_job_raises_failure():
    account_id = 1234
    job_id = 1234
    run_job = DbtCloudRunJob(
        cause="foo", account_id=account_id, job_id=job_id, token="foo"
    )
    with Mocker() as m:
        m.register_uri(
            "POST",
            f"https://cloud.getdbt.com/api/v2/accounts/{account_id}/jobs/{job_id}/run/",
            status_code=123,
            reason="foo",
        )
        with pytest.raises(FAIL) as exc:
            run_job.run()
    assert "foo" in str(exc)


def test_dbt_cloud_run_job_trigger_job():
    account_id = 1234
    job_id = 1234
    run_job = DbtCloudRunJob(
        cause="foo", account_id=account_id, job_id=job_id, token="foo"
    )
    with Mocker() as m:
        m.register_uri(
            "POST",
            f"https://cloud.getdbt.com/api/v2/accounts/{account_id}/jobs/{job_id}/run/",
            status_code=200,
            json={"data": {"foo": "bar"}},
        )
        r = run_job.run()
    assert r == {"foo": "bar"}