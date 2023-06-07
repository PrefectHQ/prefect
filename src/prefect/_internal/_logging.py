import logging


class SafeLogger(logging.Logger):
    """
    A logger with extensions for safe emission of logs in our concurrency tooling.
    """

    def isEnabledFor(self, level: int):
        # Override `logger.isEnabledFor` to avoid taking a logging lock which can cause
        # deadlocks during complex concurrency handling
        from prefect.settings import PREFECT_LOGGING_INTERNAL_LEVEL

        return level >= logging._nameToLevel[PREFECT_LOGGING_INTERNAL_LEVEL.value()]

    def getChild(self, suffix: str):
        logger = super().getChild(suffix)
        logger.__class__ = SafeLogger
        return logger


# Use `getLogger` to retain `logger.Manager` behavior
logger = logging.getLogger("prefect._internal")

# Update the class to inject patched behavior
logger.__class__ = SafeLogger
