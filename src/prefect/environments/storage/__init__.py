"""
The Prefect Storage interface encapsulates logic for storing, serializing and even running Flows.  Each storage unit is able to store _multiple_ flows (possibly with the constraint of name uniqueness within a given unit), and exposes the following methods and attributes:

- a name attribute
- a `flows` attribute that is a dictionary of Flows -> location
- an `add_flow(flow: Flow) -> str` method for adding flows to Storage, and that will return the location of the given flow in the Storage unit
- the `__contains__(self, obj) -> bool` special method for determining whether the Storage contains a given Flow
- one of `get_flow(flow_location: str)` or `get_env_runner(flow_location: str)` for retrieving a way of interfacing with either `flow.run` or a `FlowRunner` for the flow; `get_env_runner` is intended for situations where flow execution can only be interacted with via environment variables
- a `build() -> Storage` method for "building" the storage
- a `serialize() -> dict` method for serializing the relevant information about this Storage for later re-use.
"""

from prefect.environments.storage.base import Storage
from prefect.environments.storage.docker import Docker
from prefect.environments.storage.bytes import Bytes
from prefect.environments.storage.local import Local
from prefect.environments.storage.memory import Memory
