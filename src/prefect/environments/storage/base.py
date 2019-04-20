"""
Storage objects are used to store Prefect flows so that they can be moved, shared, and
executed. This is the base Storage class which requires all subclasses to implement
a particular interface:
    - an `add_flow` method for adding new flows to Storage
    - a `get_flow_location` method for determining a Flow's location in Storage
    - a `build` method for building the Storage object
    - the `__contains__` special method for determining whether a given Flow is in this Storage
    - either a `get_runner` method for retrieving a runner-like object for the flow, or a `get_env_runner`
        method for exposing an interface for setting environment variables for a flow run

The `build` function is meant to take a Prefect flow and store it
then return that Storage object which contains information about how and where the flow
is stored.
"""

from abc import ABCMeta, abstractmethod
from typing import Any

import prefect


class Storage(metaclass=ABCMeta):
    """
    Base class for Storage objects.
    """

    def __init__(self) -> None:
        pass

    def get_env_runner(flow_location: str) -> Any:
        """
        Given a flow_location within this Storage object, returns something with a
        `run()` method which accepts a collection of environment variables for running the flow.

        Args:
            - flow_location (str): the location of a flow within this Storage

        Returns:
            - a runner interface (something with a `run()` method for running the flow)
        """
        raise NotImplementedError()

    def get_runner(flow_location: str, return_flow: bool = True) -> Any:
        """
        Given a flow_location within this Storage object, returns something with a
        `run()` method which accepts the standard runner kwargs and can run the flow.

        Args:
            - flow_location (str): the location of a flow within this Storage
            - return_flow (bool, optional): whether to return the full Flow object
                or a `FlowRunner`; defaults to `True`

        Returns:
            - a runner interface (something with a `run()` method for running the flow)
        """
        raise NotImplementedError()

    @abstractmethod
    def add_flow(flow: "prefect.core.flow.Flow") -> str:
        """
        Method for adding a new flow to this Storage object.

        Args:
            - flow (Flow): a Prefect Flow to add

        Returns:
            - str: the location of the newly added flow in this Storage object
        """
        pass

    @property
    def name(self):
        """
        Name of the environment.  Can be overriden.
        """
        return type(self).__name__

    @abstractmethod
    def __contains__(self, obj):
        """
        Method for determining whether an object is contained within this storage.
        """
        pass

    @property
    def flow_location(self):
        "not sure if property or 'empty' attribute"
        # optionally set at serialization time for an individual flow
        pass

    @abstractmethod
    def get_flow_location(flow):
        """
        Given a flow, retrieves its location within this Storage object.

        Args:
            - flow (Flow): a Prefect Flow contained within this Storage

        Returns:
            - str: the location of the Flow

        Raises:
            - ValueError: if the provided Flow does not live in this Storage object
        """
        pass

    @abstractmethod
    def build(self) -> "Storage":
        """
        Build the Storage object.

        Returns:
            - Storage: a Storage object that contains information about how and where
                each flow is stored
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
