import os
import sys

import pytest
import responses
from responses import matchers

from prefect import Flow
from prefect.tasks.dbt import DbtCloudRunJob, DbtShellTask
from prefect.tasks.dbt.dbt_cloud_utils import (
    USER_AGENT_HEADER,
    TriggerDbtCloudRunFailed,
)

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
    assert dbt_run_job_task.domain == "cloud.getdbt.com"


def test_dbt_cloud_run_job_create_task_with_domain():
    dbt_run_job_task = DbtCloudRunJob(
        account_id=1234,
        token="xyz",
        job_id=1234,
        cause="foo",
        domain="cloud.corp.getdbt.com",
    )

    assert dbt_run_job_task.account_id == 1234
    assert dbt_run_job_task.token == "xyz"
    assert dbt_run_job_task.job_id == 1234
    assert dbt_run_job_task.cause == "foo"
    assert dbt_run_job_task.domain == "cloud.corp.getdbt.com"


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

    with responses.RequestsMock() as rsps:
        rsps.add(
            responses.POST,
            f"https://cloud.getdbt.com/api/v2/accounts/{account_id}/jobs/{job_id}/run/",
            status=123,
            match=[matchers.header_matcher(USER_AGENT_HEADER)],
        )

        run_job = DbtCloudRunJob(
            cause="foo", account_id=account_id, job_id=job_id, token="foo"
        )
        with pytest.raises(TriggerDbtCloudRunFailed):
            run_job.run()


def test_dbt_cloud_run_corp_job_raises_failure():
    account_id = 1234
    job_id = 1234

    with responses.RequestsMock() as rsps:
        rsps.add(
            responses.POST,
            f"https://cloud.corp.getdbt.com/api/v2/accounts/{account_id}/jobs/{job_id}/run/",
            status=123,
            match=[matchers.header_matcher(USER_AGENT_HEADER)],
        )

        run_job = DbtCloudRunJob(
            cause="foo",
            account_id=account_id,
            job_id=job_id,
            token="foo",
            domain="cloud.corp.getdbt.com",
        )
        with pytest.raises(TriggerDbtCloudRunFailed):
            run_job.run()


def test_dbt_cloud_run_job_trigger_job():
    account_id = 1234
    job_id = 1234
    with responses.RequestsMock() as rsps:
        rsps.add(
            responses.POST,
            f"https://cloud.getdbt.com/api/v2/accounts/{account_id}/jobs/{job_id}/run/",
            status=200,
            json={"data": {"foo": "bar"}},
            match=[matchers.header_matcher(USER_AGENT_HEADER)],
        )

        run_job = DbtCloudRunJob(
            cause="foo", account_id=account_id, job_id=job_id, token="foo"
        )
        r = run_job.run()

        assert r == {"foo": "bar"}


def test_dbt_cloud_run_job_trigger_job_custom_domain():
    account_id = 1234
    job_id = 1234
    with responses.RequestsMock() as rsps:
        rsps.add(
            responses.POST,
            f"https://cloud.corp.getdbt.com/api/v2/accounts/{account_id}/jobs/{job_id}/run/",
            status=200,
            json={"data": {"foo": "bar"}},
            match=[matchers.header_matcher(USER_AGENT_HEADER)],
        )

        run_job = DbtCloudRunJob(
            cause="foo",
            account_id=account_id,
            job_id=job_id,
            token="foo",
            domain="cloud.corp.getdbt.com",
        )
        r = run_job.run()

        assert r == {"foo": "bar"}


def test_dbt_cloud_run_job_trigger_job_with_wait():
    account_id = 1234
    job_id = 1234
    with responses.RequestsMock() as rsps:
        rsps.add(
            responses.POST,
            f"https://cloud.getdbt.com/api/v2/accounts/{account_id}/jobs/{job_id}/run/",
            status=200,
            json={"data": {"id": 1}},
            match=[matchers.header_matcher(USER_AGENT_HEADER)],
        )

        rsps.add(
            responses.GET,
            f"https://cloud.getdbt.com/api/v2/accounts/{account_id}/runs/1/",
            status=200,
            json={
                "data": {"id": 1, "status": 10, "finished_at": "2019-08-24T14:15:22Z"}
            },
            match=[matchers.header_matcher(USER_AGENT_HEADER)],
        )

        rsps.add(
            responses.GET,
            f"https://cloud.getdbt.com/api/v2/accounts/{account_id}/runs/1/artifacts/",
            status=200,
            json={"data": ["manifest.json", "run_results.json", "catalog.json"]},
            match=[matchers.header_matcher(USER_AGENT_HEADER)],
        )

        run_job = DbtCloudRunJob(
            cause="foo",
            account_id=account_id,
            job_id=job_id,
            token="foo",
            wait_for_job_run_completion=True,
        )
        r = run_job.run()

        assert r == {
            "id": 1,
            "status": 10,
            "finished_at": "2019-08-24T14:15:22Z",
            "artifact_urls": [
                f"https://cloud.getdbt.com/api/v2/accounts/{account_id}/runs/1/artifacts/manifest.json",
                f"https://cloud.getdbt.com/api/v2/accounts/{account_id}/runs/1/artifacts/run_results.json",
                f"https://cloud.getdbt.com/api/v2/accounts/{account_id}/runs/1/artifacts/catalog.json",
            ],
        }


def test_dbt_cloud_run_job_trigger_job_with_wait_custom():
    account_id = 1234
    job_id = 1234
    with responses.RequestsMock() as rsps:
        rsps.add(
            responses.POST,
            f"https://cloud.corp.getdbt.com/api/v2/accounts/{account_id}/jobs/{job_id}/run/",
            status=200,
            json={"data": {"id": 1}},
            match=[matchers.header_matcher(USER_AGENT_HEADER)],
        )

        rsps.add(
            responses.GET,
            f"https://cloud.corp.getdbt.com/api/v2/accounts/{account_id}/runs/1/",
            status=200,
            json={
                "data": {"id": 1, "status": 10, "finished_at": "2019-08-24T14:15:22Z"}
            },
            match=[matchers.header_matcher(USER_AGENT_HEADER)],
        )

        rsps.add(
            responses.GET,
            f"https://cloud.corp.getdbt.com/api/v2/accounts/{account_id}/runs/1/artifacts/",
            status=200,
            json={"data": ["manifest.json", "run_results.json", "catalog.json"]},
            match=[matchers.header_matcher(USER_AGENT_HEADER)],
        )

        run_job = DbtCloudRunJob(
            cause="foo",
            account_id=account_id,
            job_id=job_id,
            token="foo",
            wait_for_job_run_completion=True,
            domain="cloud.corp.getdbt.com",
        )
        r = run_job.run()

        assert r == {
            "id": 1,
            "status": 10,
            "finished_at": "2019-08-24T14:15:22Z",
            "artifact_urls": [
                f"https://cloud.corp.getdbt.com/api/v2/accounts/{account_id}/runs/1/artifacts/manifest.json",
                f"https://cloud.corp.getdbt.com/api/v2/accounts/{account_id}/runs/1/artifacts/run_results.json",
                f"https://cloud.corp.getdbt.com/api/v2/accounts/{account_id}/runs/1/artifacts/catalog.json",
            ],
        }


def test_user_agent():
    assert "prefect" in USER_AGENT_HEADER["user-agent"]
