from prefect.utilities.collections import AutoEnum


class WorkerStatus(AutoEnum):
    """Enumeration of worker statuses."""

    ONLINE = AutoEnum.auto()
    OFFLINE = AutoEnum.auto()