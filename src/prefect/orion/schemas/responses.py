from prefect.orion.utilities.enum import AutoEnum


class SetStateStatus(AutoEnum):
    ACCEPT = AutoEnum.auto()
    REJECT = AutoEnum.auto()
    ABORT = AutoEnum.auto()
