from prefect.storage import S3 as _S3
from prefect.environments.storage.base import _DeprecatedStorageMixin


class S3(_S3, _DeprecatedStorageMixin):
    pass
