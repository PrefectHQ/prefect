import warnings

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
    """DEPRECATED - use `prefect.storage.get_default_storage_class` instead."""
    warnings.warn(
        "`prefect.environments.storage.get_default_storage_class` is deprecated, "
        "use `prefect.storage.get_default_storage_class` instead",
        stacklevel=2,
    )
    from prefect.storage import get_default_storage_class

    return get_default_storage_class()
