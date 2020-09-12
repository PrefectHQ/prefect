from distutils.version import LooseVersion

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


def get_flow_run_command(flow_run: GraphQLResult) -> str:
    """
    Determine the flow run command to use based on a flow's version. This is due to a command
    deprecation in `0.13.0` where `execute cloud-flow` was changes to `execute flow-run`

    Args:
        - flow_run (GraphQLResult): A GraphQLResult flow run object

    Returns:
        - str: a prefect CLI command to execute a flow run
    """
    core_version = getattr(flow_run.flow, "core_version", None) or "0.0.0"

    if LooseVersion(core_version) < LooseVersion("0.13.0"):
        return "prefect execute cloud-flow"

    return "prefect execute flow-run"
