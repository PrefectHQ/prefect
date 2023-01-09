from prefect import flow, get_run_logger
from prefect.deployments import Deployment


@flow
def hello(name: str = "world"):
    get_run_logger().info(f"Hello {name}!")


if __name__ == "__main__":
    # Create deployment
    if hasattr(Deployment, "build_from_flow"):
        deployment = Deployment.build_from_flow(
            flow=hello, name="test-deployment", apply=True
        )
    else:
        deployment = Deployment(
            name="test-deployment",
            flow_name=hello.name,
        )

    # Update deployment
    deployment.tags = ["test"]
    deployment.apply()
