from pydantic import (
    ConfigDict,
)

from prefect._internal.schemas.bases import PrefectBaseModel


class TaskRunInput(PrefectBaseModel):
    """
    Base class for classes that represent inputs to task runs, which
    could include, constants, parameters, or other task runs.
    """

    model_config = ConfigDict(frozen=True)

    input_type: str
