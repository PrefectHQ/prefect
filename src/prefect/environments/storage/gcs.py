from prefect.storage import GCS as _GCS
from prefect.environments.storage.base import _DeprecatedStorageMixin


class GCS(_GCS, _DeprecatedStorageMixin):
    pass
