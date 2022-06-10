from abc import abstractmethod
from typing import Any, Optional

from prefect.blocks.core import Block, register_block


class NotificationBlock(Block):
    """
    A `Block` base class for sending notifications.
    """

    @abstractmethod
    async def notify(self, data: Any):
        """
        Send a notification
        """


@register_block
class DebugPrintNotification(NotificationBlock):
    """
    Notification block that prints a message, useful for debugging.
    """

    _block_type_name = "Debug Print Notification"
    # singleton block name
    _block_document_name = "Debug Print Notification"

    async def notify(self, data: Any):
        print(data)
