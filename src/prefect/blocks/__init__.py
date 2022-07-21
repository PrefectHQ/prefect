# ensure core blocks are registered

import prefect.blocks.notifications
import prefect.blocks.system

__all__ = ["notifications", "storage", "system"]
