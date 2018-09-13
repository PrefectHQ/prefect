# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

import logging
import os
import re

import toml
from typing import Union
from prefect.utilities import collections

DEFAULT_CONFIG = os.path.join(os.path.dirname(__file__), "config.toml")
ENV_VAR_PREFIX = "PREFECT"
INTERPOLATION_REGEX = re.compile(r"\${(.[^${}]*)}")


class Config(collections.DotDict):
    pass


def string_to_type(val: str) -> Union[bool, int, float, str]:
    """
    Helper function for transforming string env var values into typed values.

    Maps:
        - "true" or "True" to `True`
        - "false" or "False" to `False`
        - integers to `int`
        - floats to `float`

    Arguments:
        - val (str): the string value of an environment variable

    Returns:
        Union[bool, int, float, str]: the type-cast env var value
    """

    # bool
    if val in ["true", "True"]:
        return True
    elif val in ["false", "False"]:
        return False

    # int
    try:
        val_as_int = int(val)
        if str(val_as_int) == val:
            return val_as_int
    except Exception:
        pass

    # float
    try:
        val_as_float = float(val)
        if str(val_as_float) == val:
            return val_as_float
    except Exception:
        pass

    # return string value
    return val


def interpolate_env_var(env_var: str) -> str:
    """
    Expands (potentially nested) env vars by repeatedly applying
    `expandvars` and `expanduser` until interpolation stops having
    any effect.
    """
    if not env_var or not isinstance(env_var, str):
        return env_var

    counter = 0

    while counter < 10:
        interpolated = os.path.expanduser(os.path.expandvars(str(env_var)))
        if interpolated == env_var:
            # if a change was made, apply string-to-type casts; otherwise leave alone
            # this is because we don't want to override TOML type-casting if this function
            # is applied to a non-interpolated value
            if counter > 1:
                interpolated = string_to_type(interpolated)
            return interpolated
        else:
            env_var = interpolated
        counter += 1


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


def load_config_file(path: str, env_var_prefix: str = None) -> Config:
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
    #     [ENV_VAR_PREFIX]__[Section]__[Optional Sub-Sections...]__[Key] = Value
    # and if it does, add it to the config file.
    if env_var_prefix:
        for env_var in os.environ:
            if env_var.startswith(env_var_prefix + "__"):

                # strip the prefix off the env var
                env_var_option = env_var[len(env_var_prefix + "__") :]

                # make sure the resulting env var has at least one delimitied section and key
                if "__" not in env_var:
                    continue

                # place the env var in the flat config as a compound key
                config_option = collections.CompoundKey(
                    env_var_option.lower().split("__")
                )
                flat_config[config_option] = string_to_type(
                    interpolate_env_var(os.getenv(env_var))
                )

    # interpolate any env vars referenced
    for k, v in list(flat_config.items()):
        flat_config[k] = interpolate_env_var(v)

    # --------------------- Interpolate other config keys -----------------
    # TOML doesn't support references to other keys... but we do!
    # This has the potential to lead to nasty recursions, so we check at most 10 times.
    # we use a set called "keys_to_check" to track only the ones of interest, so we aren't
    # checking every key every time.
    keys_to_check = set(flat_config.keys())

    for _ in range(10):

        # iterate over every key and value to check if the value uses interpolation
        for k in list(keys_to_check):

            # if the value isn't a string, it can't be a reference, so we exit
            if not isinstance(flat_config[k], str):
                keys_to_check.remove(k)
                continue

            # see if the ${...} syntax was used in the value and exit if it wasn't
            match = INTERPOLATION_REGEX.search(flat_config[k])
            if not match:
                keys_to_check.remove(k)
                continue

            # the matched_string includes "${}"; the matched_key is just the inner value
            matched_string = match.group(0)
            matched_key = match.group(1)

            # get the referenced key from the config value
            ref_key = collections.CompoundKey(matched_key.split("."))
            # get the value corresponding to the referenced key
            ref_value = flat_config[ref_key]

            # if the matched was the entire value, replace it with the interpolated value
            if flat_config[k] == matched_string:
                flat_config[k] = ref_value
            # if it was a partial match, then drop the interpolated value into the string
            else:
                flat_config[k] = flat_config[k].replace(
                    matched_string, str(ref_value), 1
                )

    return collections.flatdict_to_dict(flat_config, dct_class=Config)


def load_configuration(
    config_path: str, env_var_prefix: str = None, merge_into_config: Config = None
) -> Config:
    """
    Given a `config_path` with a toml configuration file, returns a Config object.

    Args:
        - config_path (str): the path to the toml configuration file
        - env_var_prefix (str): if provided, environment variables starting with this prefix
            will be added as configuration settings.
        - merge_into_config (Config): if provided, the configuration loaded from
            `config_path` will be merged into a copy of this configuration file. The merged
            Config is returned.
    """

    # load default config
    config = load_config_file(config_path, env_var_prefix=env_var_prefix or "")

    if merge_into_config is not None:
        config = collections.merge_dicts(merge_into_config, config)

    validate_config(config)

    return config


config = load_configuration(config_path=DEFAULT_CONFIG, env_var_prefix=ENV_VAR_PREFIX)

# if user config exists, load and merge it with default config
if os.path.isfile(config.get("general", {}).get("user_config_path", "")):
    config = load_configuration(
        config_path=config.general.user_config_path,
        env_var_prefix=ENV_VAR_PREFIX,
        merge_into_config=config,
    )

configure_logging(logger_name="Prefect")
