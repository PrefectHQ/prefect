from prefect.storage import Azure as _Azure
from prefect.environments.storage.base import _DeprecatedStorageMixin


class Azure(_Azure, _DeprecatedStorageMixin):
    pass
