from prefect.storage import Webhook as _Webhook
from prefect.environments.storage.base import _DeprecatedStorageMixin


class Webhook(_Webhook, _DeprecatedStorageMixin):
    pass
