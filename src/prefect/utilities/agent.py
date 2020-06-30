import prefect
from prefect.utilities.graphql import GraphQLResult


def get_flow_image(flow_run: GraphQLResult) -> str:
    """
    Retrieve the image to use for this flow run deployment. Will start by looking for
    an `image` value in the flow's `environment.metadata`. If not found then it will fall
    back to using the `flow.storage`.

    Args:
        - flow_run (GraphQLResult): A GraphQLResult flow run object

    Returns:
        - str: a full image name to use for this flow run

    Raises:
        - ValueError: if deployment attempted on unsupported Storage type and `image` not
            present in environment metadata
    """
    environment = prefect.serialization.environment.EnvironmentSchema().load(
        flow_run.flow.environment
    )
    if hasattr(environment, "metadata") and hasattr(environment.metadata, "image"):
        return environment.metadata.get("image")
    else:
        storage = prefect.serialization.storage.StorageSchema().load(
            flow_run.flow.storage
        )
        if not isinstance(
            prefect.serialization.storage.StorageSchema().load(flow_run.flow.storage),
            prefect.environments.storage.Docker,
        ):
            raise ValueError(
                f"Storage for flow run {flow_run.id} is not of type Docker and "
                f"environment has no `image` attribute in the metadata field."
            )

        return storage.name
