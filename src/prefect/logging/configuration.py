import logging
import logging.config
import os
import re
import string
import warnings
from functools import partial
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from prefect.settings import SETTINGS
from prefect.utilities.collections import dict_to_flatdict, flatdict_to_dict

# This path will be used if `PREFECT_LOGGING_SETTINGS_PATH` is null
DEFAULT_LOGGING_SETTINGS_PATH = Path(__file__).parent / "logging.yml"

# Stores the configuration used to setup logging in this Python process
PROCESS_LOGGING_CONFIG: Optional[Dict[str, Any]] = None

# Regex call to replace non-alphanumeric characters to '_' to create a valid env var
to_envvar = partial(re.sub, re.compile(r"[^0-9a-zA-Z]+"), "_")


def load_logging_config(path: Path) -> dict:
    """
    Loads logging configuration from a path allowing override from the environment.
    """
    template = string.Template(path.read_text())

    # Build a mapping from environment variable names to values
    mapping = {}
    for name, value in SETTINGS.model_dump().items():
        if value is not None:
            # Construct the environment variable name using the prefix
            env_var_name = SETTINGS.model_config.get("env_prefix") + name.upper()
            mapping[env_var_name] = str(value)

    # Now do the substitution
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=DeprecationWarning)
        config = yaml.safe_load(template.substitute(mapping))

    # Load overrides from the environment
    flat_config = dict_to_flatdict(config)

    for key_tup, val in flat_config.items():
        env_var = to_envvar("PREFECT_LOGGING_" + "_".join(key_tup)).upper()
        env_val = os.environ.get(env_var)
        if env_val:
            val = env_val

        # Reassign the updated value
        flat_config[key_tup] = val

    return flatdict_to_dict(flat_config)


def setup_logging(incremental: Optional[bool] = None) -> dict:
    """
    Sets up logging.

    Returns the config used.
    """
    global PROCESS_LOGGING_CONFIG

    # If the user has specified a logging path and it exists we will ignore the
    # default entirely rather than dealing with complex merging
    config = load_logging_config(
        (
            SETTINGS.logging_settings_path
            if SETTINGS.logging_settings_path
            and SETTINGS.logging_settings_path.exists()
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

    for logger_name in SETTINGS.logging_extra_loggers:
        logger = logging.getLogger(logger_name)
        for handler in extra_config.handlers:
            if not config["incremental"]:
                logger.addHandler(handler)
            if logger.level == logging.NOTSET:
                logger.setLevel(extra_config.level)
            logger.propagate = extra_config.propagate

    PROCESS_LOGGING_CONFIG = config

    return config
