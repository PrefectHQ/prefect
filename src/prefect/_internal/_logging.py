import logging
import sys

from typing_extensions import Self

if sys.version_info < (3, 11):

    def getLevelNamesMapping() -> dict[str, int]:
        return getattr(logging, "_nameToLevel").copy()
else:
    getLevelNamesMapping = logging.getLevelNamesMapping  # novermin


class SafeLogger(logging.Logger):
    """
    A logger with extensions for safe emission of logs in our concurrency tooling.
    """

    def isEnabledFor(self, level: int):
        # Override `logger.isEnabledFor` to avoid taking a logging lock which can cause
        # deadlocks during complex concurrency handling
        from prefect.settings import PREFECT_LOGGING_INTERNAL_LEVEL

        internal_level = getLevelNamesMapping()[PREFECT_LOGGING_INTERNAL_LEVEL.value()]

        return level >= internal_level

    def getChild(self, suffix: str) -> Self:
        logger = super().getChild(suffix)
        logger.__class__ = self.__class__
        return logger


# Use `getLogger` to retain `logger.Manager` behavior
logger = logging.getLogger("prefect._internal")

# Update the class to inject patched behavior
logger.__class__ = SafeLogger
