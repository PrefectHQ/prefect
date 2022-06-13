# ensure core blocks are registered
from prefect.blocks import storage
from prefect.blocks import notifications

__all__ = ['notifications', 'storage']
