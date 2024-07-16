from prefect.utilities.collections import AutoEnum


class LogSort(AutoEnum):
    """Defines log sorting options."""

    TIMESTAMP_ASC = AutoEnum.auto()
    TIMESTAMP_DESC = AutoEnum.auto()
