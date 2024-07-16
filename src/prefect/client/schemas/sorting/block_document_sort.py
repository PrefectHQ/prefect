from prefect.utilities.collections import AutoEnum


class BlockDocumentSort(AutoEnum):
    """Defines block document sorting options."""

    NAME_DESC = AutoEnum.auto()
    NAME_ASC = AutoEnum.auto()
    BLOCK_TYPE_AND_NAME_ASC = AutoEnum.auto()
