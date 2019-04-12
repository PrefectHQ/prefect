import prefect
from prefect.environments.storage import Storage


class Docker(Storage):
    """"""

    def __init__(self) -> None:
        pass

    def build(self, flow: "prefect.Flow") -> "Storage":
        pass
