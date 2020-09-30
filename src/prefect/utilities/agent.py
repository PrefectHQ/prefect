from distutils.version import LooseVersion

from prefect.utilities.graphql import GraphQLResult


def get_flow_image(flow_run: GraphQLResult) -> str:
    """
    Retrieve the image to use for this flow run deployment.

    Args:
        - flow_run (GraphQLResult): A GraphQLResult flow run object

    Returns:
        - str: a full image name to use for this flow run

    Raises:
        - ValueError: if deployment attempted on unsupported Storage type and `image` not
            present in environment metadata
    """
    from prefect.environments.storage import Docker
    from prefect.serialization.storage import StorageSchema
    from prefect.serialization.run_config import RunConfigSchema
    from prefect.serialization.environment import EnvironmentSchema

    storage = StorageSchema().load(flow_run.flow.storage)
    if getattr(flow_run.flow, "run_config", None) is not None:
        run_config = RunConfigSchema().load(flow_run.flow.run_config)
        if isinstance(storage, Docker):
            return storage.name
        elif getattr(run_config, "image", None) is not None:
            return run_config.image
        else:
            # core_version should always be present, but just in case
            version = flow_run.flow.get("core_version") or "latest"
            return f"prefecthq/prefect:all_extras-{version}"
    else:
        environment = EnvironmentSchema().load(flow_run.flow.environment)
        if hasattr(environment, "metadata") and hasattr(environment.metadata, "image"):
            return environment.metadata.get("image")
        elif isinstance(storage, Docker):
            return storage.name
        raise ValueError(
            f"Storage for flow run {flow_run.id} is not of type Docker and "
            f"environment has no `image` attribute in the metadata field."
        )


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
