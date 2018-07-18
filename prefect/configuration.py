import logging
import os
import re

import toml

import prefect
from prefect.utilities import collections

DEFAULT_CONFIG = os.path.join(os.path.dirname(prefect.__file__), "configuration.toml")
USER_CONFIG = "~/.prefect/configuration.toml"
ENV_VAR_PREFIX = "PREFECT"
INTERPOLATION_REGEX = re.compile(r"\${(.[^${}]*)}")


class Config(collections.DotDict):
    def __repr__(self) -> str:
        return "<Config: {}>".format(", ".join(sorted(self.keys())))


def interpolate_env_var(env_var: str) -> str:
    """
    Expands (potentially nested) env vars by repeatedly applying
    `expandvars` and `expanduser` until interpolation stops having
    any effect.
    """
    if not env_var or not isinstance(env_var, str):
        return env_var
    while True:
        substituted = os.path.expanduser(os.path.expandvars(str(env_var)))
        if substituted == env_var:
            return substituted
        else:
            env_var = substituted


def create_user_config(dest_path: str, source_path: str = DEFAULT_CONFIG) -> None:
    """
    Copies the default configuration to a user-customizable file at `dest_path`
    """
    dest_path = interpolate_env_var(dest_path)
    if os.path.isfile(dest_path):
        raise ValueError("File already exists: {}".format(dest_path))
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)

    with open(dest_path, "w") as dest:
        with open(source_path, "r") as source:
            dest.write(source.read())


# Logging ---------------------------------------------------------------------


def configure_logging(logger_name: str) -> None:
    logger = logging.getLogger(logger_name)
    handler = logging.StreamHandler()
    formatter = logging.Formatter(config.logging.format)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(getattr(logging, config.logging.level))


# Validation ------------------------------------------------------------------


def validate_config(config: Config) -> None:
    """
    Placeholder for future config validation. For example, invalid values could raise an error.
    """
    pass


# Load configuration ----------------------------------------------------------


def load_config_file(path: str, env_var_prefix: str=ENV_VAR_PREFIX) -> Config:
    """
    Loads a configuration file from a path, optionally merging it into an existing
    configuration.
    """

    # load the configuration file
    config = toml.load(interpolate_env_var(path))

    # toml supports nested dicts, so we work with a flattened representation to do any
    # requested interpolation
    flat_config = collections.dict_to_flatdict(config)

    # --------------------- Interpolate env vars -----------------------
    # check if any env var sets a configuration value with the format:
    # [ENV_VAR_PREFIX]__[Section]__[Optional Sub-Sections...]__[Key] = Value
    for env_var in os.environ:
        if env_var.startswith(env_var_prefix + "__"):

            # strip the prefix off the env var
            env_var_option = env_var[len(env_var_prefix + "__") :]

            # make sure the resulting env var has at least one delimitied section and key
            if "__" not in env_var:
                continue

            # place the env var in the flat config as a compound key
            config_option = collections.CompoundKey(env_var_option.lower().split("__"))
            flat_config[config_option] = interpolate_env_var(os.getenv(env_var))

    # interpolate any env vars referenced
    for k, v in list(flat_config.items()):
        flat_config[k] = interpolate_env_var(v)

    # --------------------- Interpolate other config keys -----------------
    # TOML doesn't support references to other keys... but we do!
    # This has the potential to lead to nasty recursions, so we check at most 10 times.
    for _ in range(10):

        # iterate over every key and value to check if the value uses interpolation
        for k, v in list(flat_config.items()):

            # if the value isn't a string, it can't be a reference, so we exit
            if not isinstance(v, str):
                continue

            # see if the ${...} syntax was used in the value and exit if it wasn't
            match = INTERPOLATION_REGEX.search(v)
            if not match:
                continue

            # the matched_string includes "${}"; the matched_key is just the inner value
            matched_string = match.group(0)
            matched_key = match.group(1)

            # get the referenced key from the config value
            ref_key = collections.CompoundKey(matched_key.split("."))
            # get the value corresponding to the referenced key
            ref_value = flat_config[ref_key]

            # if the matched was the entire value, replace it with the interpolated value
            if v == matched_string:
                flat_config[k] = ref_value
            # if it was a partial match, then drop the interpolated value into the string
            else:
                flat_config[k] = v.replace(matched_string, str(ref_value), 1)

    return collections.flatdict_to_dict(flat_config, dct_class=Config)



def load_configuration(
    default_config_path: str, user_config_path: str, env_var_prefix: str = None
) -> Config:
    default_config = load_config_file(
        default_config_path, env_var_prefix=env_var_prefix
    )
    try:
        create_user_config(user_config_path)
    except Exception:
        pass
    user_config = load_config_file(user_config_path, env_var_prefix=env_var_prefix)

    config = collections.merge_dicts(default_config, user_config)

    validate_config(config)

    return config


config = load_configuration(
    default_config_path=DEFAULT_CONFIG,
    user_config_path=USER_CONFIG,
    env_var_prefix=ENV_VAR_PREFIX,
)

configure_logging(logger_name="Prefect")
