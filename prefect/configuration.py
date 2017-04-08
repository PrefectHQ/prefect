import prefect.configuration
import base64
from configparser import ConfigParser
import hashlib
import logging
import os
import re

SYSTEM_NAMESPACE = 'prefect'

config = ConfigParser()

_default_config_files = [
    os.path.join(
        os.path.dirname(__file__), 'default_configuration', 'prefect.cfg'),
]
_test_config_files = [
    os.path.join(
        os.path.dirname(__file__), 'default_configuration', 'prefect.cfg'),
]

env_var_re = re.compile(
    '^PREFECT__(?P<section>\S+)__(?P<option>\S+)', re.IGNORECASE)


def _add_default_config_file(config_file):
    """
    Adds a new default configuration file
    """
    _default_config_files.append(config_file)


def _add_test_config_file(config_file):
    """
    Adds a new test configuration file
    """
    _test_config_files.append(config_file)


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


def load_config_files(config_files=None, append=False):
    """
    Loads a new Prefect configuration.

    Prefect configurations are loaded in the following sequence:
        - any files in the _config_file list
        - any file passed to this method

    Any configuration options set by environment variables take precedance over
    all loaded files.

    Args:
        config_file (str): the path to a Prefect configuration file

        append (bool): if True, the passed file will be loaded on top of
            the existing configuration; if False the default configuration
            will be loaded first, followed by the passed file.

    """
    global config
    all_config_files = []

    if not append:
        all_config_files.extend(_default_config_files)
        if os.getenv('PREFECT_CONFIG'):
            all_config_files.append(os.getenv('PREFECT_CONFIG'))

    if config_files is not None:
        if isinstance(config_files, str):
            config_files = [config_files]
        all_config_files.extend(config_files)

    all_config_files = [expand(c) for c in all_config_files]

    if not append:
        config.clear()

    config.read(all_config_files)

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


def load_test_config():
    return load_config_files(config_files=_test_config_files)


def load_user_config():
    load_config_files(config_files='~/.prefect/config', append=True)


def load_configuration():
    load_config_files()

    # Test Mode
    if os.getenv('PREFECT_TEST_MODE', '').upper() in ('1', 'YES', 'TRUE', 'ON'):
        load_test_config()
    else:
        load_user_config()


load_configuration()
