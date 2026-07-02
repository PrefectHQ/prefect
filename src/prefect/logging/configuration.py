from __future__ import annotations

import logging
import logging.config
import os
import re
import string
import warnings
from functools import lru_cache, partial
from pathlib import Path
from typing import Any, Callable

import yaml

from prefect.settings import (
    PREFECT_LOGGING_EXTRA_LOGGERS,
    PREFECT_LOGGING_SETTINGS_PATH,
    get_current_settings,
)
from prefect.utilities.collections import dict_to_flatdict, flatdict_to_dict

# This path will be used if `PREFECT_LOGGING_SETTINGS_PATH` is null
DEFAULT_LOGGING_SETTINGS_PATH = Path(__file__).parent / "logging.yml"

# Stores the configuration used to setup logging in this Python process
PROCESS_LOGGING_CONFIG: dict[str, Any] = {}

# Regex call to replace non-alphanumeric characters to '_' to create a valid env var
to_envvar: Callable[[str], str] = partial(re.sub, re.compile(r"[^0-9a-zA-Z]+"), "_")


def load_logging_config(path: Path) -> dict[str, Any]:
    """
    Loads logging configuration from a path allowing override from the environment
    """
    current_settings = get_current_settings()
    template = string.Template(path.read_text())

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=DeprecationWarning)
        config = yaml.safe_load(
            # Substitute settings into the template in format $SETTING / ${SETTING}
            template.substitute(
                current_settings.to_environment_variables(include_aliases=True)
            )
        )

    # Load overrides from the environment and from settings (profiles/config files)
    flat_config = dict_to_flatdict(config)
    setting_overrides = current_settings.logging.overrides

    for key_tup, val in flat_config.items():
        env_var = to_envvar("PREFECT_LOGGING_" + "_".join(key_tup)).upper()
        # Generate a valid environment variable with nesting indicated with '_'
        env_val = os.environ.get(env_var)
        if env_val is None:
            env_val = setting_overrides.get(env_var)
        if env_val:
            if isinstance(val, list):
                val = env_val.split(",")
            else:
                val = env_val

        # reassign the updated value
        flat_config[key_tup] = val

    return flatdict_to_dict(flat_config)


@lru_cache(maxsize=8)
def get_valid_setting_overrides(path: Path) -> frozenset[str]:
    """Return the set of valid `PREFECT_LOGGING_*` override names for a logging
    configuration file.

    These correspond to every nested key in the logging configuration file
    (logging.yml), e.g. `PREFECT_LOGGING_LOGGERS_PREFECT_FLOW_RUNS_LEVEL`. Used by the
    CLI to validate `prefect config set` keys. The file is parsed lazily (only when
    this is called) and the result is cached, so it never runs on import.
    """
    if not path.exists():
        return frozenset()
    config = yaml.safe_load(path.read_text())
    if not isinstance(config, dict):
        return frozenset()
    return frozenset(
        to_envvar("PREFECT_LOGGING_" + "_".join(key_tup)).upper()
        for key_tup in dict_to_flatdict(config)
    )


def ensure_logging_setup() -> None:
    """
    Ensure Prefect logging is configured in this process, calling
    `setup_logging` only if it has not already been called.

    Use this in remote execution environments (e.g. Dask/Ray workers) where
    the normal SDK entry point (`import prefect`) may not have triggered
    logging configuration.
    """
    if not PROCESS_LOGGING_CONFIG:
        setup_logging()


def setup_logging(incremental: bool | None = None) -> dict[str, Any]:
    """
    Sets up logging.

    Returns the config used.
    """
    global PROCESS_LOGGING_CONFIG

    # If the user has specified a logging path and it exists we will ignore the
    # default entirely rather than dealing with complex merging
    config = load_logging_config(
        (
            PREFECT_LOGGING_SETTINGS_PATH.value()
            if PREFECT_LOGGING_SETTINGS_PATH.value().exists()
            else DEFAULT_LOGGING_SETTINGS_PATH
        )
    )

    incremental = (
        incremental if incremental is not None else bool(PROCESS_LOGGING_CONFIG)
    )

    # Perform an incremental update if setup has already been run
    config.setdefault("incremental", incremental)

    root_logger = logging.getLogger()
    if root_logger.handlers and not incremental:
        from prefect.logging.handlers import PrefectConsoleHandler

        has_user_handlers = any(
            hasattr(handler, "formatter")
            and handler.formatter is not None
            and not isinstance(handler, PrefectConsoleHandler)
            and not handler.__class__.__name__.startswith("_")
            and not handler.__class__.__name__ == "LogCaptureHandler"
            for handler in root_logger.handlers
        )
        if has_user_handlers:
            config.pop("root", None)

    try:
        logging.config.dictConfig(config)
    except ValueError:
        if incremental:
            setup_logging(incremental=False)

    # Copy configuration of the 'prefect.extra' logger to the extra loggers
    extra_config = logging.getLogger("prefect.extra")

    for logger_name in PREFECT_LOGGING_EXTRA_LOGGERS.value():
        logger = logging.getLogger(logger_name)
        if not config["incremental"]:
            for handler in extra_config.handlers:
                logger.addHandler(handler)

    PROCESS_LOGGING_CONFIG.update(config)

    return config
