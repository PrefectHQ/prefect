"""
The Prefect Storage interface encapsulates logic for storing, serializing and even running Flows.
Each storage unit is able to store _multiple_ flows (possibly with the constraint of name uniqueness
within a given unit), and exposes the following methods and attributes:

- a `flows` attribute that is a dictionary of flow name  -> location
- an `add_flow(flow: Flow) -> str` method for adding flows to Storage, and that will return the intended
location of the given flow in the Storage unit (note flow uploading/saving does not happen until `build`)
- the `__contains__(self, obj) -> bool` special method for determining whether the Storage contains a
given Flow
- one of `get_flow(flow_location: str)` for retrieving a way of interfacing with either `flow.run` or a
`FlowRunner` for the flow
- a `build() -> Storage` method for "building" the storage. In storage options where flows are stored in
an external service (such as S3 and the filesystem) the flows are uploaded/saved during this step
- a `serialize() -> dict` method for serializing the relevant information about this Storage for later
re-use.

The default flow storage mechanism is based on pickling the flow object using `cloudpickle` and the
saving that pickle to a location. Flows can optionally also be stored as a script using the
`stored_as_script` boolean kwarg. For more information visit the
[file-based storage idiom](/core/idioms/file-based.html).
"""

from warnings import warn

import prefect
from prefect import config
from .base import Storage
from .docker import Docker
from .local import Local
from .azure import Azure
from .gcs import GCS
from .s3 import S3
from .github import GitHub
from .gitlab import GitLab
from .bitbucket import Bitbucket
from .codecommit import CodeCommit
from .webhook import Webhook


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
                f"Could not import {config_value}; using prefect.storage.Local instead."
            )
            return Local
    else:
        return config_value
