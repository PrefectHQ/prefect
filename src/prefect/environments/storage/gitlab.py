from prefect.storage import GitLab as _GitLab
from prefect.environments.storage.base import _DeprecatedStorageMixin


class GitLab(_GitLab, _DeprecatedStorageMixin):
    pass
