# ensure core blocks are registered

import prefect.blocks.system
import prefect.blocks.notifications
import prefect.blocks.storage

__all__ = ["notifications", "storage", "system"]
