from prefect.storage import GitHub as _GitHub
from prefect.environments.storage.base import _DeprecatedStorageMixin


class GitHub(_GitHub, _DeprecatedStorageMixin):
    pass
