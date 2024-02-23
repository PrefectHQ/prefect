import logging

from prefect.utilities.names import obfuscate


class ObfuscateApiKeyFilter(logging.Filter):
    """
    A logging filter that obfuscates any string that matches the obfuscate_string function.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        # Need to import here to avoid circular imports
        from prefect.settings import PREFECT_API_KEY

        if PREFECT_API_KEY:
            record.msg = record.msg.replace(
                PREFECT_API_KEY.value(), obfuscate(PREFECT_API_KEY.value())
            )
        return True
