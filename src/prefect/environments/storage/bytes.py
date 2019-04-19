import prefect
from prefect.environments.storage import Storage

# TODO: This is unimplemented as of https://github.com/PrefectHQ/prefect/pull/936
class Bytes(Storage):
    """
    Bytes storage.
    """

    def __init__(self) -> None:
        pass

    def build(self, flow: "prefect.Flow") -> "Storage":
        """
        Build the Bytes storage object.

        Args:
            - flow (prefect.Flow): Flow to be stored

        Returns:
            - Bytes: a new Bytes storage object that contains information about how and
                where the flow is stored.
        """
        return Bytes()
