"""
Storage objects are used to store Prefect flows so that they can be moved, shared, and
executed. This is the base Storage class which requires all subclasses to implement
a `build` function.

The `build` function is meant to take a Prefect flow and store it
then return that Storage object which contains information about how and where the flow
is stored.
"""

import prefect


class Storage:
    """
    Base class for Storage objects.
    """

    def __init__(self) -> None:
        pass

    def build(self, flow: "prefect.Flow") -> "Storage":
        """
        Build the Storage object.

        Args:
            - flow (prefect.Flow): Flow to be stored

        Returns:
            - Storage: a Storage object that contains information about how and where
                the flow is stored
        """
        raise NotImplementedError()

    def serialize(self) -> dict:
        """
        Returns a serialized version of the Storage object

        Returns:
            - dict: the serialized Storage
        """
        schema = prefect.serialization.storage.StorageSchema()
        return schema.dump(self)
