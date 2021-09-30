# versioneer
from . import _version

__version__ = _version.get_versions()["version"]

from prefect.utilities.settings import settings
from prefect.utilities.logging import setup_logging

setup_logging(settings)

# Import the serializers so they are registered
import prefect.serializers

# User-facing API
from prefect.orion.schemas.states import State
from prefect.flows import flow
from prefect.tasks import task
from prefect.engine import tags
