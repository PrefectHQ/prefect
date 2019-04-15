import prefect
from prefect.environments.storage import Storage

class Bytes(Storage):
    """"""

    def __init__(self) -> None:
        pass

    def build(self, flow: "prefect.Flow") -> "Storage":
        """"""
        raise NotImplementedError()
