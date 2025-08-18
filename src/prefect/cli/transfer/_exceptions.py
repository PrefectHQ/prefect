class TransferSkipped(Exception):
    """
    Exception raised when a resource is skipped during transfer.
    """

    def __init__(self, reason: str):
        self.reason = reason

    def __str__(self) -> str:
        return self.reason
