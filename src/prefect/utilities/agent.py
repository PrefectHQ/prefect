from packaging.version import parse

from prefect.utilities.graphql import GraphQLResult


def get_flow_image(flow_run: GraphQLResult, default: str = None) -> str:
    """
    Retrieve the image to use for this flow run deployment.

    Args:
        - flow_run (GraphQLResult): A GraphQLResult flow run object
        - default (str, optional): A default image to use. If not specified,
            The `prefecthq/prefect` image corresponding with the flow's prefect
            version will be used.

    Returns:
        - str: a full image name to use for this flow run

    Raises:
        - ValueError: if deployment attempted on unsupported Storage type and `image` not
            present in environment metadata
    """
    from prefect.storage import Docker
    from prefect.serialization.storage import StorageSchema
    from prefect.serialization.run_config import RunConfigSchema

    has_run_config = getattr(flow_run, "run_config", None) is not None

    storage = StorageSchema().load(flow_run.flow.storage)

    # Precedence:
    # - Image on docker storage
    # - Image on run_config
    # - Provided default
    # - `prefecthq/prefect` for flow's core version

    if isinstance(storage, Docker):
        return storage.name

    if has_run_config:
        run_config = RunConfigSchema().load(flow_run.run_config)
        if getattr(run_config, "image", None) is not None:
            return run_config.image

    if default is not None:
        return default

    # core_version should always be present, but just in case
    version = flow_run.flow.get("core_version") or "latest"
    cleaned_version = version.split("+")[0]

    return f"prefecthq/prefect:{cleaned_version}"


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

    if parse(core_version) < parse("0.13.0"):
        return "prefect execute cloud-flow"

    return "prefect execute flow-run"
