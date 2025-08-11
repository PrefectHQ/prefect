from __future__ import annotations

import logging
import logging.config
import os
import re
import string
import warnings
from functools import partial
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
    and profile settings
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

    # Load overrides from profile and environment
    flat_config = dict_to_flatdict(config)
    
    # Apply settings overrides
    settings_dict = current_settings.to_environment_variables(include_aliases=True)
    for setting_key, setting_value in settings_dict.items():
        if not setting_key.startswith("PREFECT_LOGGING_"):
            continue
            
        path = setting_key[16:].lower()  # Remove prefix
        if not path:
            continue
            
        parts = path.split("_")
        
        # Try different key combinations to match existing config
        candidates = []
        if parts[0] == "loggers" and len(parts) > 2:
            # Try logger.name.setting and logger_name.setting patterns
            candidates = [
                (parts[0], ".".join(parts[1:-1]), parts[-1]),
                (parts[0], "_".join(parts[1:-1]), parts[-1])
            ]
        elif parts[0] in ["formatters", "handlers"] and len(parts) >= 3:
            # Handlers/formatters may have underscores in names
            candidates = [(parts[0], parts[1], "_".join(parts[2:]))]
        
        # Add default interpretation
        candidates.append(tuple(parts))
        
        # Find first matching key
        key_tup = next((k for k in candidates if k in flat_config), None)
        
        if key_tup and key_tup in flat_config:
            # Skip if overridden by environment variable
            env_key = to_envvar(f"PREFECT_LOGGING_{path}").upper()
            if not os.environ.get(env_key):
                # Apply value with proper type
                flat_config[key_tup] = (
                    setting_value.split(",") 
                    if isinstance(flat_config[key_tup], list)
                    else setting_value
                )

    # Then check environment variables (higher priority)
    for key_tup, val in flat_config.items():
        env_val = os.environ.get(
            # Generate a valid environment variable with nesting indicated with '_'
            to_envvar("PREFECT_LOGGING_" + "_".join(key_tup)).upper()
        )
        if env_val:
            if isinstance(val, list):
                val = env_val.split(",")
            else:
                val = env_val

            # reassign the updated value
            flat_config[key_tup] = val

    return flatdict_to_dict(flat_config)


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
