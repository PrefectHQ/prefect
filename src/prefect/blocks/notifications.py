from abc import abstractmethod

from prefect.blocks.core import Block
from prefect.utilities.dispatch import register_type


class NotificationBlock(Block):
    """
    A `Block` base class for sending notifications.
    """

    @abstractmethod
    async def notify(self, subject: str, body: str):
        """
        Send a notification
        """


@register_type
class DebugPrintNotification(NotificationBlock):
    """
    Notification block that prints a message, useful for debugging.
    """

    _block_type_name = "Debug Print Notification"
    # singleton block name
    _block_document_name = "Debug Print Notification"

    async def notify(self, subject: str, body: str):
        print(body)
