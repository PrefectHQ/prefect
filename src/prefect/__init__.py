# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

import prefect.utilities
from prefect.configuration import config

from prefect.utilities.context import context

from prefect.client import Client
import prefect.schedules
import prefect.serializers
import prefect.triggers
import prefect.environments

from prefect.core import Task, Flow, Parameter
import prefect.core.registry
import prefect.engine
import prefect.tasks
import prefect.flows
from prefect.utilities.tasks import task, tags, unmapped

from ._version import get_versions

__version__ = get_versions()["version"]
del get_versions

if prefect.config.registry.startup_registry_path:
    prefect.core.registry.load_serialized_registry_from_path(
        prefect.config.registry.startup_registry_path
    )
