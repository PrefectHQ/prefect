"""
prefect dev build-image
"""
from prefect import flow, get_run_logger, task
from prefect.deployments import Deployment
from prefect.infrastructure.docker import DockerContainer, ImagePullPolicy
from prefect.packaging import DockerPackager
from prefect.software import PythonEnvironment


@task
def say_hi(input_: str):
    logger = get_run_logger()
    logger.info("Hello %s!", input_)


@flow
def docker_flow_with_packager(input_: str = "from Docker"):
    say_hi(input_)


Deployment(
    flow=docker_flow_with_packager,
    name="docker_packager",
    packager=DockerPackager(
        base_image="prefecthq/prefect:dev-python3.9",
        python_environment=PythonEnvironment(
            python_version="3.9",
            pip_requirements=["requests==2.28.0"],
        ),
    ),
    infrastructure=DockerContainer(
        image_pull_policy=ImagePullPolicy.IF_NOT_PRESENT,
        env=dict(PREFECT_LOGGING_LEVEL="DEBUG"),
    ),
)

if __name__ == "__main__":
    docker_flow_with_packager()
