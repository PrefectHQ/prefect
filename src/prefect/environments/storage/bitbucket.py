from prefect.storage import Bitbucket as _Bitbucket
from prefect.environments.storage.base import _DeprecatedStorageMixin


class Bitbucket(_Bitbucket, _DeprecatedStorageMixin):
    pass
