import pytest

from prefect.contrib.tasks.databricks import DatabricksSubmitRun


@pytest.fixture(scope="session")
def job_config():

    config = {
        "run_name": "Prefect Test",
        "new_cluster": {
            "spark_version": "6.6.x-scala2.11",
            "num_workers": 0,
            "node_type_id": "Standard_D3_v2",
        },
        "spark_python_task": {
            "python_file": f"dbfs:/FileStore/tables/runner.py",
            "parameters": [1],
        },
    }

    return config


def test_initialization(job_config):

    task = DatabricksSubmitRun(json=job_config)

    assert "run_name" in task.json
    assert "new_cluster" in task.json
    assert "spark_python_task" in task.json


def test_raises_if_invalid_host(job_config):

    task = DatabricksSubmitRun(json=job_config)

    with pytest.raises(Exception, match="API requests to Databricks failed"):
        task.run()
