from abc import abstractmethod
from typing import Any, Optional


from prefect.blocks.core import Block, register_block


class NotificationBlock(Block):
    """
    A `Block` base class for sending notifications.

    Implementers must provide methods to read and write bytes. When data is persisted,
    an object of type `T` is returned that may be later be used to retrieve the data.

    The type `T` should be JSON serializable.
    """

    _block_schema_type: Optional[str] = "NOTIFICATION"

    @abstractmethod
    async def send(self, data: Any):
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

    async def send(self, data: Any):
        print(data)
