from prefect.utilities.collections import AutoEnum


class WorkPoolStatus(AutoEnum):
    """Enumeration of work pool statuses."""

    READY = AutoEnum.auto()
    NOT_READY = AutoEnum.auto()
    PAUSED = AutoEnum.auto()


class WorkerStatus(AutoEnum):
    """Enumeration of worker statuses."""

    ONLINE = AutoEnum.auto()
    OFFLINE = AutoEnum.auto()


class DeploymentStatus(AutoEnum):
    """Enumeration of deployment statuses."""

    READY = AutoEnum.auto()
    NOT_READY = AutoEnum.auto()
