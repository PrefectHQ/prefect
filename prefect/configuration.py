import prefect.configuration
import base64
from configparser import ConfigParser
from cryptography.fernet import Fernet
import logging
import os
import re

env_var_re = re.compile(
    '^PREFECT__(?P<section>\S+)__(?P<option>\S+)', re.IGNORECASE)
DEFAULT_CONFIG = os.path.join(os.path.dirname(prefect.__file__), 'prefect.cfg')
USER_CONFIG = '~/.prefect/prefect.cfg'


def str_to_bool(string):
    true_strings = ['1', 'true', 't', 'yes', 'y']
    false_strings = ['0', 'false', 'f', 'no', 'n', 'none']
    if string.lower() in true_strings:
        return True
    elif string.lower() in false_strings:
        return False
    else:
        return ValueError(f'Unrecognized boolean string: "{string}"')


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


def create_user_config(config_file):
    """
    Copies the default configuration to a user-customizable file
    """
    config_file = expand(config_file)
    if os.path.isfile(config_file):
        raise ValueError('File already exists: {}'.format(config_file))
    os.makedirs(os.path.dirname(config_file), exist_ok=True)

    with open(config_file, 'w') as fw:
        with open(DEFAULT_CONFIG, 'r') as fr:
            template = fr.read()
            key = Fernet.generate_key().decode()
            template = template.replace('<<REPLACE WITH FERNET KEY>>', key)
            fw.write(template)


# Logging ---------------------------------------------------------------------


def configure_logging(config, logger_name):
    logger = logging.getLogger(logger_name)
    handler = logging.StreamHandler()
    formatter = logging.Formatter(config.get('logging', 'format'))
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(getattr(logging, config.get('logging', 'level')))


# Validation ------------------------------------------------------------------


def validate_config(config):
    pass


# Load configuration ----------------------------------------------------------


def load_config_file(config_file, config=None, env_var_re=None):
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

    if config_file is None:
        return config

    config.read(expand(config_file))

    # overwrite environment variables
    if env_var_re:
        for ev in os.environ:
            match = re.match(env_var_re, ev)
            if match:
                config.set(
                    section=match.groupdict()['section'].lower(),
                    option=match.groupdict()['option'].lower(),
                    value=os.environ[ev])

    validate_config(config)
    return config


def load_configuration(
        default_config, user_config, env_var_config, config, env_var_re):
    """
    Loads a prefect configuration by first loading the default_config file
    and then loading a user configuration. If an env_var_config is supplied, it is
    checked for the location of a configuration file; otherwise the user_config
    argument is used.
    """
    default_config = load_config_file(
        default_config, config=config, env_var_re=env_var_re)
    user_config = os.getenv(env_var_config, user_config)
    try:
        create_user_config(config_file=user_config)
    except ValueError:
        pass
    config = load_config_file(
        user_config, config=default_config, env_var_re=env_var_re)
    return config


config = load_configuration(
    default_config=DEFAULT_CONFIG,
    user_config=USER_CONFIG,
    env_var_config='PREFECT_CONFIG',
    config=None,
    env_var_re=env_var_re)

configure_logging(config, logger_name='Prefect')

# load unit test configuration
if config.getboolean('tests', 'test_mode'):
    config = load_configuration(
        user_config=os.path.join(
            os.path.dirname(__file__), 'prefect_tests.cfg'),
        env_var_config='PREFECT_SERVER_TESTS_CONFIG',
        config=config)
