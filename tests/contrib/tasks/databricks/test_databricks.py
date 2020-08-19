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


def test_raises_if_invalid_host(job_config):

    with pytest.raises(TypeError, match="argument of type"):
        task = DatabricksSubmitRun(json=job_config)
        task.run()
