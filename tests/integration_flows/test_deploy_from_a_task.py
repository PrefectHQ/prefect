from pathlib import Path

from prefect import flow, task


@flow
def to_be_deployed():
    pass


@task
def to_be_deployed_task():
    current_file = Path(__file__)
    to_be_deployed.from_source(
        source=str(current_file.parent),
        entrypoint=f"{current_file.name}:to_be_deployed",
    ).deploy(name="test", work_pool_name="default-docker-container")


def test_deploy_from_a_task():
    """Test for deploy_from_a_task."""
    to_be_deployed_task()
