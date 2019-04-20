import filecmp
import json
import logging
import os
import shutil
import tempfile
import textwrap
import uuid
from typing import Dict, Iterable, List

import docker

import prefect
from prefect.environments.storage import Storage
from prefect.utilities.exceptions import SerializationError


# lastly, the job yml can be populated by CloudEnvironment so that
# run_flow in the CLI command accepts the name of the correct flow.
# cloud-side, agent then calls environment.execute(storage, flow)


class Memory(Storage):
    """
    Base class for Storage objects.
    """

    def __init__(self) -> None:
        self.flows = dict()  # type: Dict[str, prefect.core.flow.Flow]
        super().__init__()

    def get_runner(flow_location: str) -> Any:
        """
        Given a flow name, returns the flow.

        Args:
            - flow_location (str): the name of the flow

        Returns:
            - Flow: the requested Flow
        """
        return self.flows[flow_location]

    def add_flow(flow: "prefect.core.flow.Flow") -> str:
        """
        Method for adding a new flow to this Storage object.

        Args:
            - flow (Flow): a Prefect Flow to add

        Returns:
            - str: the location of the newly added flow in this Storage object
        """
        self.flows[flow.name] = flow
        return flow.name

    def __contains__(self, obj):
        """
        Method for determining whether an object is contained within this storage.
        """
        return obj in self.flows

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
        if not flow in self:
            raise ValueError("Flow is not conatined in this Storage")

        return [loc for loc, f in self.flows.items() if f.name == flow.name].pop()

    def build(self) -> "Storage":
        """
        Build the Storage object.

        Returns:
            - Storage: a Storage object that contains information about how and where
                each flow is stored
        """
        return self
