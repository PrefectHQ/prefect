from prefect.configuration import config

import prefect.utilities
from prefect.utilities.context import context

import prefect.schedules
import prefect.serializers
import prefect.triggers
import prefect.environments

from prefect.core import Task, Flow, Parameter
import prefect.core.registry
import prefect.engine
import prefect.tasks
import prefect.flows
from prefect.utilities.tasks import task, tags, group

# from prefect.client import Client

from ._version import get_versions

__version__ = get_versions()["version"]
del get_versions

if prefect.config.registry.load_on_startup:
    prefect.core.registry.load_serialized_registry_from_path(
        prefect.config.registry.load_on_startup
    )
