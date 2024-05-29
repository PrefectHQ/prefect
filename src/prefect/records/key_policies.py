from prefect.utilities.collections import AutoEnum


class KeyPolicy:
    pass


class DEFAULT(KeyPolicy):
    "Execution run ID only"
    pass


RUN_ID = DEFAULT


class NONE(KeyPolicy):
    "ignore key policies altogether, always run - prevents persistence"
    pass


class TASK_DEF(KeyPolicy):
    pass


class INPUTS(KeyPolicy):
    """
    Exposes flag for whether to include flow parameters as well.

    And exclude/include config.
    """

    pass


class CUSTOM(KeyPolicy):
    """
    Can provide a key_fn
    """
