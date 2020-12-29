from prefect.storage import Local as _Local
from prefect.environments.storage.base import _DeprecatedStorageMixin


class Local(_Local, _DeprecatedStorageMixin):
    pass
