import re
import logging
import os
import random
import uuid
from string import ascii_letters, digits, punctuation

import toml
from cryptography.fernet import Fernet

import prefect
from prefect.utilities import collections

DEFAULT_CONFIG = os.path.join(os.path.dirname(prefect.__file__), 'prefect.toml')
USER_CONFIG = '~/.prefect/prefect.toml'
ENV_VAR_PREFIX = 'PREFECT'
INTERPOLATION_REGEX = re.compile(r'\${(.*)}+')

def expand(env_var):
    """
    Expands (potentially nested) env vars by repeatedly applying
    `expandvars` and `expanduser` until interpolation stops having
    any effect.
    """
    if not env_var or not isinstance(env_var, str):
        return env_var
    while True:
        interpolated = os.path.expanduser(os.path.expandvars(str(env_var)))
        if interpolated == env_var:
            return interpolated
        else:
            env_var = interpolated


def create_user_config(path, source=DEFAULT_CONFIG):
    """
    Copies the default configuration to a user-customizable file
    """
    config_file = expand(path)
    if os.path.isfile(config_file):
        raise ValueError('File already exists: {}'.format(config_file))
    os.makedirs(os.path.dirname(config_file), exist_ok=True)

    def quote(s):
        return '"' + s + '"'

    with open(config_file, 'w') as fw:
        with open(source, 'r') as fr:
            src = fr.read()
            counter = 0

            while '"<<FERNET KEY>>"' in src:
                key = Fernet.generate_key().decode()
                src = src.replace('"<<FERNET KEY>>"', quote(key), 1)
                counter += 1
                if counter > 100:
                    raise ValueError('Unexpected interpolation error.')

            while '"<<SECRET>>"' in src:
                chars = ascii_letters + digits + '!@#$%^&*()[]<>,.-'
                secret = ''.join(random.choice(chars) for i in range(32))
                src = src.replace('"<<SECRET>>"', quote(secret), 1)
                counter += 1
                if counter > 100:
                    raise ValueError('Unexpected interpolation error.')

            while '"<<UUID>>"' in src:
                src = src.replace('"<<UUID>>"', quote(str(uuid.uuid4())), 1)
                counter += 1
                if counter > 100:
                    raise ValueError('Unexpected interpolation error.')

            fw.write(src)


# Logging ---------------------------------------------------------------------


def configure_logging(logger_name):
    logger = logging.getLogger(logger_name)
    handler = logging.StreamHandler()
    formatter = logging.Formatter(config.logging.format)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(getattr(logging, config.logging.level))


# Validation ------------------------------------------------------------------


def validate_config(config):
    pass


# Load configuration ----------------------------------------------------------


def load_config_file(path, existing_config=None):

    config = toml.load(expand(path))
    flat_config = collections.dict_to_flatdict(config)

    # set configuration from env vars
    for env_var in os.environ:
        if not env_var.startswith(ENV_VAR_PREFIX):
            continue
        sections = collections.CompoundKey(env_var.lower().split('__')[1:])
        if sections:
            flat_config[sections] = expand(os.getenv(env_var))

    # expand configuration referencing env vars
    for k, v in list(flat_config.items()):
        flat_config[k] = expand(v)

    # process interpolation of any variable referencing another with ${}
    # process up to 10 links
    for i in range(10):
        for k, v in list(flat_config.items()):
            if not isinstance(v, str):
                continue
            match = INTERPOLATION_REGEX.search(v)
            if not match:
                continue
            referenced_key = collections.CompoundKey(match.group(1).split('.'))
            referenced_value = flat_config[referenced_key]
            if v == match.group(0):
                flat_config[k] = referenced_value
            else:
                flat_config[k] = v.replace(match.group(0), referenced_value, 1)

    config = collections.flatdict_to_dict(flat_config)

    if existing_config is not None:
        config = collections.merge_dicts(existing_config, config)

    return collections.dict_to_dotdict(config)


def load_configuration(default_config, user_config, env_var=None):
    user_config_path = os.getenv(env_var, user_config)
    config = load_config_file(default_config)
    try:
        create_user_config(user_config_path)
    except Exception:
        pass
    config = load_config_file(user_config_path, existing_config=config)
    return config


config = load_configuration(
    default_config=DEFAULT_CONFIG,
    user_config=USER_CONFIG,
    env_var='PREFECT_CONFIG')

# load unit test configuration
if config.tests.test_mode:
    config = load_configuration(
        default_config=DEFAULT_CONFIG,
        user_config=os.path.join(
            os.path.dirname(__file__), 'prefect_tests.toml'),
        env_var='PREFECT_TESTS_CONFIG')

configure_logging(logger_name='Prefect')
