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

from warnings import warn

import prefect
from prefect import config
from prefect.environments.storage.base import Storage
from prefect.environments.storage.docker import Docker
from prefect.environments.storage.local import Local
from prefect.environments.storage.azure import Azure
from prefect.environments.storage.gcs import GCS
from prefect.environments.storage.s3 import S3
from prefect.environments.storage.github import GitHub


def get_default_storage_class() -> type:
    """
    Returns the `Storage` class specified in
    `prefect.config.flows.defaults.storage.default_class`. If the value is a string, it will
    attempt to load the already-imported object. Otherwise, the value is returned.

    Defaults to `Local` if the string config value can not be loaded
    """
    config_value = config.flows.defaults.storage.default_class
    if isinstance(config_value, str):
        try:
            return prefect.utilities.serialization.from_qualified_name(config_value)
        except ValueError:
            warn(
                "Could not import {}; using "
                "prefect.environments.storage.Local instead.".format(config_value)
            )
            return Local
    else:
        return config_value
