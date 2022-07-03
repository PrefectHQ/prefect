
import pytest


from prefect.tasks.databricks import (
    DatabricksRunNow,
    DatabricksSubmitRun,
    DatabricksGetJobID,
)


def test_raises_if_invalid_host_submitrun(job_config):

    # from prefect.tasks.secrets import PrefectSecret
    # conn = PrefectSecret('DATABRICKS_CONNECTION_STRING')
    # task = DatabricksSubmitRun(databricks_conn_secret=conn, json=job_config)

    with pytest.raises(AttributeError, match="object has no attribute"):
        task = DatabricksSubmitRun(
            databricks_conn_secret={"host": "", "token": ""}, json=job_config
        )
        task.run()


def test_raises_if_invalid_host_runnow(notebook_job_config):

    # from prefect.tasks.secrets import PrefectSecret
    # conn = PrefectSecret('DATABRICKS_CONNECTION_STRING')
    # task = DatabricksSubmitRun(databricks_conn_secret=conn, json=job_config)

    with pytest.raises(AttributeError, match="object has no attribute"):
        task = DatabricksRunNow(
            databricks_conn_secret={"host": "", "token": ""}, json=notebook_job_config
        )
        task.run()


def test_ensure_run_id_not_defined_within_class_arguments(job_config):
    assert not hasattr(job_config, "run_id")


class TestDatabricksRunNowAttributeOverrides:
    """Test various expected attribute override behavior with `DatabricksRunNow.run`"""

    def test_without_overrides(self, run_now_task_template):
        run_now_task_template.run()

        run_now_json = run_now_task_template.json
        assert run_now_json.get("job_id") == "1"
        assert run_now_json.get("notebook_params", {}).get("dry-run") == "true"
        assert (
            run_now_json.get("notebook_params", {}).get("oldest-time-to-consider")
            == "1457570074236"
        )
        assert run_now_json.get("python_params") == ["python-param1", "python-param2"]
        assert run_now_json.get("spark_submit_params") == [
            "spark-param1",
            "spark-param2",
        ]
        assert run_now_json.get("jar_params") == ["jar-param1", "jar-param2"]

    def test_with_job_id_override(self, run_now_task_template):
        run_now_task_template.run(job_id="42")
        assert run_now_task_template.json.get("job_id") == "42"

    def test_with_notebook_params_override(self, run_now_task_template):
        run_now_task_template.run(notebook_params={"dry-run": "false"})

        run_now_json = run_now_task_template.json
        assert run_now_json.get("notebook_params", {}).get("dry-run") == "false"
        assert (
            run_now_json.get("notebook_params", {}).get("oldest-time-to-consider")
            == "1457570074236"
        )

    def test_with_python_params_override(self, run_now_task_template):
        run_now_task_template.run(python_params=["python-param3"])
        assert run_now_task_template.json.get("python_params") == ["python-param3"]

    def test_with_spark_submit_params_override(self, run_now_task_template):
        run_now_task_template.run(spark_submit_params=["spark-param3"])
        assert run_now_task_template.json.get("spark_submit_params") == ["spark-param3"]

    def test_with_jar_params_override(self, run_now_task_template):
        run_now_task_template.run(jar_params=["jar-param3"])
        assert run_now_task_template.json.get("jar_params") == ["jar-param3"]

    def test_with_json_override(self, run_now_task_template):
        run_now_task_template.run(
            json={"job_id": "123"},
            notebook_params={"notebookparam1": "notebookvalue1"},
        )

        run_now_json = run_now_task_template.json
        assert len(run_now_json) == 2
        assert run_now_json.get("job_id") == "123"
        assert (
            run_now_json.get("notebook_params", {}).get("notebookparam1")
            == "notebookvalue1"
        )

    def test_ensure_run_id_not_defined_within_class_arguments(
        self, run_now_task_template
    ):
        assert not hasattr(run_now_task_template, "run_id")


class TestDatabricksGetJobID:
    def test_initialization(self):
        DatabricksGetJobID({})

    def test_initialization_passes_to_task_constructor(self):
        task = DatabricksGetJobID(
            databricks_conn_secret={"host": "host_name"},
            search_limit=1,
        )
        assert task.databricks_conn_secret == {"host": "host_name"}
        assert task.search_limit == 1

    def test_raises_cant_find_matching_job_name(self, get_jobid_task_template):
        with pytest.raises(ValueError, match="name"):
            get_jobid_task_template.run(job_name="none")

    def test_raises_on_duplicate_job_name(self, get_jobid_task_template):
        with pytest.raises(ValueError, match="duplicate"):
            get_jobid_task_template.run(job_name="duplicate")

    def test_find_matching_job_name(self, get_jobid_task_template):
        task_result = get_jobid_task_template.run(job_name="job_name")
        assert task_result == 76
