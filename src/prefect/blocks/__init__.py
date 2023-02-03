# ensure core blocks are registered

import prefect.blocks.notifications
import prefect.blocks.system
import prefect.blocks.webhook

__all__ = ["notifications", "system", "webhook"]
