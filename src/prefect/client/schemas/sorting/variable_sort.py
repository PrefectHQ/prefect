from prefect.utilities.collections import AutoEnum


class VariableSort(AutoEnum):
    """Defines variables sorting options."""

    CREATED_DESC = "CREATED_DESC"
    UPDATED_DESC = "UPDATED_DESC"
    NAME_DESC = "NAME_DESC"
    NAME_ASC = "NAME_ASC"
