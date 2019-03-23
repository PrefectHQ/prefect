import datetime
import logging
import os
import re
from typing import Any, Optional, Union, cast

import toml

from prefect.utilities import collections

DEFAULT_CONFIG = os.path.join(os.path.dirname(__file__), "config.toml")
ENV_VAR_PREFIX = "PREFECT"
INTERPOLATION_REGEX = re.compile(r"\${(.[^${}]*)}")


class Config(collections.DotDict):

    __protect_critical_keys__ = False

    def __getattr__(self, attr: str) -> Any:
        """
        This method helps mypy discover attribute types without annotations
        """
        if attr in self:
            return super().__getattr__(attr)  # type: ignore
        else:
            raise AttributeError("Config has no key '{}'".format(attr))

    def copy(self) -> "Config":
        """
        Create a copy of the config. Each level of the Config is a new Config object, so
        modifying keys won't affect the original Config object. However, values are not
        deep-copied, and mutations can affect the original.
        """
        new_config = Config()
        for key, value in self.items():
            if isinstance(value, Config):
                value = value.copy()
            new_config[key] = value
        return new_config

    def get_nested(self, key: str, default: Any = None) -> Any:
        """
        Retrieves a (possibly nested) config key's value, creating intermediate keys if
        necessary

        For example:
        >>> config = Config(a=Config(b=Config(c=5)))
        >>> assert config.get_nested('a.b.c') == 5

        >>> config = Config()
        >>> assert config.get_nested('a.b.c') is None

        Args:
            - key (str): a key, indicated nested keys by separating them with '.'
            - default (Any): a value to return if the key is not found
        """
        tmp_val = self
        for k in key.split("."):
            if isinstance(tmp_val, Config) and k in tmp_val:
                tmp_val = tmp_val[k]
            else:
                return default
        return tmp_val

    def set_nested(self, key: str, value: Any) -> None:
        """
        Sets a (possibly nested) config key to have some value. Creates intermediate keys
        if necessary.

        For example:
        >>> config = Config()
        >>> config.set_nested('a.b.c', 5)
        >>> assert config.a.b.c == 5

        Args:
            - key (str): a key, indicated nested keys by separating them with '.'
            - value (Any): a value to set

        """
        config = self
        keys = key.split(".")
        for k in keys[:-1]:
            # get the value of the config under the provided key
            new_config = config.setdefault(k, Config())
            # if the value is not a config, then we are overwriting an existing config setting
            if not isinstance(new_config, Config):
                # assign a new config to the key
                new_config = Config()
                config[k] = new_config
            # get the new config so we can continue into the nested keys
            config = new_config

        config[keys[-1]] = value

    def setdefault_nested(self, key: str, value: Any) -> Any:
        """
        Sets a (possibly nested) config key to have some value, if it doesn't already exist.
        Creates intermediate keys if necessary.

        For example:
        >>> config = Config()
        >>> config.setdefault_nested('a.b.c', 5)
        >>> assert config.a.b.c == 5
        >>> config.setdefault_nested('a.b.c', 10)
        >>> assert config.a.b.c == 5

        Args:
            - key (str): a key, indicated nested keys by separating them with '.'
            - value (Any): a value to set

        Returns:
            Any: the value at the provided key

        """
        config = self
        keys = key.split(".")
        for k in keys[:-1]:
            config = config.setdefault(k, Config())
        if keys[-1] not in config:
            config[keys[-1]] = value
        return config[keys[-1]]


def string_to_type(val: str) -> Union[bool, int, float, str]:
    """
    Helper function for transforming string env var values into typed values.

    Maps:
        - "true" (any capitalization) to `True`
        - "false" (any capitalization) to `False`
        - integers to `int`
        - floats to `float`

    Arguments:
        - val (str): the string value of an environment variable

    Returns:
        Union[bool, int, float, str]: the type-cast env var value
    """

    # bool
    if val.upper() == "TRUE":
        return True
    elif val.upper() == "FALSE":
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


def interpolate_env_var(env_var: str) -> Optional[Union[bool, int, float, str]]:
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
                interpolated = string_to_type(interpolated)  # type: ignore
            return interpolated
        else:
            env_var = interpolated
        counter += 1

    return None


def create_user_config(dest_path: str, source_path: str = DEFAULT_CONFIG) -> None:
    """
    Copies the default configuration to a user-customizable file at `dest_path`
    """
    dest_path = cast(str, interpolate_env_var(dest_path))
    if os.path.isfile(dest_path):
        raise ValueError("File already exists: {}".format(dest_path))
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)

    with open(dest_path, "w") as dest:
        with open(source_path, "r") as source:
            dest.write(source.read())


# Process Config -------------------------------------------------------------


def process_task_defaults(config: Config) -> Config:
    """
    Converts task defaults from basic types to Python objects like timedeltas

    Args:
        - config (Config): the configuration to modify
    """
    # make sure defaults exists
    defaults = config.setdefault_nested("tasks.defaults", Config())

    # max_retries defaults to 0 if not set, False, or None
    if not defaults.setdefault("max_retries", 0):
        defaults.max_retries = 0
    defaults.max_retries = defaults.get("max_retries", 0) or 0

    # retry_delay defaults to None if not set - also check for False because TOML has no NULL
    if defaults.setdefault("retry_delay", False) is False:
        defaults.retry_delay = None
    elif isinstance(defaults.retry_delay, int):
        defaults.retry_delay = datetime.timedelta(seconds=defaults.retry_delay)

    # timeout defaults to None if not set - also check for False because TOML has no NULL
    if defaults.setdefault("timeout", False) is False:
        defaults.timeout = None
    elif isinstance(defaults.timeout, int):
        defaults.timeout = datetime.timedelta(seconds=defaults.timeout)

    return config


# Validation ------------------------------------------------------------------


def validate_config(config: Config) -> None:
    """
    Placeholder for future config validation. For example, invalid values could raise an error.
    """
    pass


# Load configuration ----------------------------------------------------------


def load_config_file(path: str, env_var_prefix: str = None, env: dict = None) -> Config:
    """
    Loads a configuration file from a path, optionally merging it into an existing
    configuration.
    """

    # load the configuration file
    config = {
        key.lower(): value
        for key, value in toml.load(cast(str, interpolate_env_var(path))).items()
    }

    # toml supports nested dicts, so we work with a flattened representation to do any
    # requested interpolation
    flat_config = collections.dict_to_flatdict(config)

    # --------------------- Interpolate env vars -----------------------
    # check if any env var sets a configuration value with the format:
    #     [ENV_VAR_PREFIX]__[Section]__[Optional Sub-Sections...]__[Key] = Value
    # and if it does, add it to the config file.

    env = cast(dict, env or os.environ)
    if env_var_prefix:

        for env_var in env:
            if env_var.startswith(env_var_prefix + "__"):

                # strip the prefix off the env var
                env_var_option = env_var[len(env_var_prefix + "__") :]

                # make sure the resulting env var has at least one delimitied section and key
                if "__" not in env_var:
                    continue

                # env vars with escaped characters are interpreted as literal "\", which
                # Python helpfully escapes with a second "\". This step makes sure that
                # escaped characters are properly interpreted.
                value = cast(str, env.get(env_var)).encode().decode("unicode_escape")

                # place the env var in the flat config as a compound key
                config_option = collections.CompoundKey(
                    env_var_option.lower().split("__")
                )
                flat_config[config_option] = string_to_type(
                    cast(str, interpolate_env_var(value))
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
            ref_value = flat_config.get(ref_key, "")

            # if the matched was the entire value, replace it with the interpolated value
            if flat_config[k] == matched_string:
                flat_config[k] = ref_value
            # if it was a partial match, then drop the interpolated value into the string
            else:
                flat_config[k] = flat_config[k].replace(
                    matched_string, str(ref_value), 1
                )

    return cast(Config, collections.flatdict_to_dict(flat_config, dct_class=Config))


def load_configuration(
    config_path: str,
    env_var_prefix: str = None,
    merge_into_config: Config = None,
    env: dict = None,
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
    config = load_config_file(config_path, env_var_prefix=env_var_prefix or "", env=env)

    if merge_into_config is not None:
        config = cast(Config, collections.merge_dicts(merge_into_config, config))

    validate_config(config)

    return config


config = load_configuration(config_path=DEFAULT_CONFIG, env_var_prefix=ENV_VAR_PREFIX)

# if user config exists, load and merge it with default config
user_config_path = config.get("user_config_path", None)
if user_config_path and os.path.isfile(user_config_path):
    config = load_configuration(
        config_path=user_config_path,
        env_var_prefix=ENV_VAR_PREFIX,
        merge_into_config=config,
    )

config = process_task_defaults(config)
