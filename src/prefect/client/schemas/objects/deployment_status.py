from prefect.utilities.collections import AutoEnum


class DeploymentStatus(AutoEnum):
    """Enumeration of deployment statuses."""

    READY = AutoEnum.auto()
    NOT_READY = AutoEnum.auto()
