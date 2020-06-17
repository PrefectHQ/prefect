from typing import TYPE_CHECKING

import prefect

if TYPE_CHECKING:
    from prefect.core.flow import Flow  # pylint: disable=W0611


def get_flow_image(flow: "Flow") -> str:
    """
    Retrieve the image to use for this flow deployment. Will start by looking for
    an `image` value in the flow's `environment.metadata`. If not found then it will fall
    back to using the `flow.storage`.

    Args:
        - flow (Flow): A flow object

    Returns:
        - str: a full image name to use for this flow run

    Raises:
        - ValueError: if deployment attempted on unsupported Storage type and `image` not
            present in environment metadata
    """
    environment = flow.environment
    if hasattr(environment, "metadata") and environment.metadata.get("image"):
        return environment.metadata.get("image", "")
    else:
        storage = flow.storage
        if not isinstance(storage, prefect.environments.storage.Docker,):
            raise ValueError(
                f"Storage for flow run {flow.name} is not of type Docker and environment has no `image` attribute in the metadata field."
            )

        return storage.name
