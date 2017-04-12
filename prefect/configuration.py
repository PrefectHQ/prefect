import prefect.configuration
import base64
from configparser import ConfigParser
import hashlib
import logging
import os
import re

SYSTEM_NAMESPACE = 'prefect'

env_var_re = re.compile(
    '^PREFECT__(?P<section>\S+)__(?P<option>\S+)', re.IGNORECASE)


def expand(env_var):
    """
    Expands (potentially nested) env vars by repeatedly applying
    `expandvars` and `expanduser` until interpolation stops having
    any effect.
    """
    if not env_var:
        return env_var
    while True:
        interpolated = os.path.expanduser(os.path.expandvars(str(env_var)))
        if interpolated == env_var:
            return interpolated
        else:
            env_var = interpolated


def create_user_config(config_file='~/.prefect/prefect.cfg'):
    """
    Copies the default configuration to a user-customizable file
    """
    config_file = expand(config_file)
    if os.path.isfile(config_file):
        raise ValueError('File already exists: {}'.format(config_file))
    os.makedirs(os.path.dirname(config_file), exist_ok=True)

    with open(config_file, 'w') as fw:
        for config_file in _default_config_files:
            with open(config_file, 'r') as fr:
                fw.write(fr.read())


# Logging ---------------------------------------------------------------------


def configure_logging(config):
    root_logger = logging.getLogger()
    handler = logging.StreamHandler()
    formatter = logging.Formatter(config.get('logging', 'format'))
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, config.get('logging', 'level')))


# Validation ------------------------------------------------------------------


def validate_config(config):
    if not config.get('flows', 'default_namespace'):
        raise ValueError(
            'No default namespace set! (config.flows.default_namespace)')
    if SYSTEM_NAMESPACE == config.get('flows', 'default_namespace'):
        raise ValueError(
            'The default namespace can not be the system namespace ("{}") '
            ' (config.flows.default_namespace)'.format(SYSTEM_NAMESPACE))


# Load configuration ----------------------------------------------------------


def load_config_file(config_file, config=None):
    """
    Loads a new Prefect configuration.

    The supplied config file is loaded on top of an existing config (
    if provided); otherwise a new config is returned.

    Any configuration options set by environment variables take precedance over
    all loaded files.

    Args:
        config_file (str): the path to a Prefect configuration file

        config (ConfigParser): an existing config that should be modified

    """
    if config is None:
        config = ConfigParser()

    config.read(expand(config_file))

    # overwrite environment variables
    for ev in os.environ:
        match = re.match(env_var_re, ev)
        if match:
            config.set(
                section=match.groupdict()['section'].lower(),
                option=match.groupdict()['option'].lower(),
                value=os.environ[ev])

    configure_logging(config)
    validate_config(config)
    return config


def load_configuration(default_config, user_config, env_var=None, config=None):
    """
    Loads a prefect configuration by first loading the default_config file
    and then loading a user configuration. If an env_var is supplied, it is
    checked for the location of a configuration file; otherwise the user_config
    argument is used.
    """
    default_config = load_config_file(default_config, config=config)
    user_config_file = os.getenv(env_var or '', user_config)
    config = load_config_file(user_config_file, config=default_config)
    return config


config = load_configuration(
    default_config=os.path.join(os.path.dirname(prefect.__file__), 'prefect.cfg'),
    user_config='~/.prefect/prefect.cfg',
    env_var='PREFECT_CONFIG',
)
