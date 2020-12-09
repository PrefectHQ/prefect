from prefect.storage import Docker as _Docker
from prefect.environments.storage.base import _DeprecatedStorageMixin


class Docker(_Docker, _DeprecatedStorageMixin):
    pass
