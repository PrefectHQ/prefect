import logging
import logging.config
from typing import Optional
from pathlib import Path
from string import Template

import yaml
import json

from prefect.core.utilities.settings import LoggingSettings


DEFAULT_LOGGING_SETTINGS_PATH = Path(__file__).parent / "logging.yml"


def load_logging_config(path: Path, settings: LoggingSettings) -> Optional[dict]:
    """
    Loads logging configuration from a path and templates `$var` strings with values
    from the `LoggingSettings` object so overrides can be provided by normal config
    methods
    """
    # Load the logging config file as a template
    template = Template(path.read_text())

    # Substitute `LoggingSettings` variables; use pydantic to ensure the settings are
    # serialized into primitive types
    config = template.substitute(**json.loads(settings.json()))
    return yaml.safe_load(config)


def setup_logging() -> None:
    settings = LoggingSettings()

    # If the user has specified a logging path and it exists we will ignore the
    # default entirely rather than dealing with complex merging
    config = load_logging_config(
        (
            settings.logging_settings_path
            if settings.settings_path.exists()
            else DEFAULT_LOGGING_SETTINGS_PATH
        ),
        settings,
    )

    logging.config.dictConfig(config)


def get_logger(name: str = None) -> logging.Logger:
    logger = logging.getLogger("prefect")
    if name is not None:
        logger = logger.getChild(name)
    return logger


class OrionHandler(logging.Handler):
    def emit(self, record: logging.LogRecord):
        # TODO: Implement a log handler that sends logs to Orion, Core uses a custom
        #       queue to batch messages but we may want to use the stdlib
        #       `MemoryHandler` as a base which implements queueing already
        #       https://docs.python.org/3/howto/logging-cookbook.html#buffering-logging-messages-and-outputting-them-conditionally
        pass


class JsonFormatter(logging.Formatter):
    # TODO: Implement a log formatter that converts `LogRecord` to JSON for Orion
    pass
