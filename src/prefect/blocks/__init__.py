# ensure core blocks are registered

import prefect.blocks.notifications as notifications
import prefect.blocks.system as system
import prefect.blocks.webhook as webhook

__all__ = ["notifications", "system", "webhook"]
