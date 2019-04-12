
import prefect

class Storage:
    """"""

    def __init__(self) -> None:
        pass

    def build(self, flow: "prefect.Flow") -> "Storage":
        """"""
        raise NotImplementedError()

    def serialize(self) -> dict:
        """"""
        # schema = prefect.serialization.storage.StorageSchema()
        # return schema.dump(self)
        pass