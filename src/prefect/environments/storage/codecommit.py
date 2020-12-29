from prefect.storage import CodeCommit as _CodeCommit
from prefect.environments.storage.base import _DeprecatedStorageMixin


class CodeCommit(_CodeCommit, _DeprecatedStorageMixin):
    pass
