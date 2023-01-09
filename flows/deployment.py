from prefect import flow, get_run_logger
from prefect.deployments import Deployment


@flow
def hello(name: str = "world"):
    get_run_logger().info(f"Hello {name}!")


if __name__ == "__main__":
    # Create deployment
    deployment = Deployment.build_from_flow(flow=flow, name="test-deployment")
    deployment.apply()

    # Update deployment
    deployment.tags = ["test"]
    deployment.apply()
