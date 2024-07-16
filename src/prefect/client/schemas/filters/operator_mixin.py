from pydantic import Field

from .operator import Operator


class OperatorMixin:
    """Base model for Prefect filters that combines criteria with a user-provided operator"""

    operator: Operator = Field(
        default=Operator.and_,
        description="Operator for combining filter criteria. Defaults to 'and_'.",
    )