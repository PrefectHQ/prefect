from prefect._internal.compatibility.deprecated import (
    register_renamed_module,
)

from . import _version
from .aiplatform import VertexAICustomTrainingJob  # noqa
from .bigquery import BigQueryWarehouse  # noqa
from .cloud_run import CloudRunJob  # noqa
from .cloud_storage import GcsBucket  # noqa
from .credentials import GcpCredentials  # noqa
from .secret_manager import GcpSecret  # noqa
from .workers.vertex import VertexAIWorker  # noqa
from .workers.cloud_run import CloudRunWorker  # noqa
from .workers.cloud_run_v2 import CloudRunWorkerV2  # noqa

register_renamed_module(
    "prefect_gcp.projects", "prefect_gcp.deployments", start_date="Jun 2023"
)
register_renamed_module(
    "prefect_gcp.worker", "prefect_gcp.workers", start_date="Sep 2023"
)


__version__ = _version.__version__
