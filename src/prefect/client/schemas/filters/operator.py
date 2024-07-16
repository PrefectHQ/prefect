from prefect.utilities.collections import AutoEnum


class Operator(AutoEnum):
    """Operators for combining filter criteria."""

    and_ = AutoEnum.auto()
    or_ = AutoEnum.auto()