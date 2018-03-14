import random
import logging
import os
import prefect
import toml
from cryptography.fernet import Fernet

from prefect.utilities.collections import dict_to_dotdict, merge_dicts

DEFAULT_CONFIG = os.path.join(os.path.dirname(prefect.__file__), 'prefect.toml')
USER_CONFIG = '~/.prefect/prefect.toml'
ENV_VAR_PREFIX = 'PREFECT'


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


def create_user_config(path):
    """
    Copies the default configuration to a user-customizable file
    """
    config_file = expand(path)
    if os.path.isfile(config_file):
        raise ValueError('File already exists: {}'.format(config_file))
    os.makedirs(os.path.dirname(config_file), exist_ok=True)

    with open(config_file, 'w') as fw:
        with open(DEFAULT_CONFIG, 'r') as fr:
            template = fr.read()
            key = Fernet.generate_key().decode()
            template = template.replace('<<REPLACE WITH FERNET KEY>>', key)
            fw.write(template)


# IDs ---------------------------------------------------------------------


def configure_ids():
    """
    Sets the random seed for generating Prefect IDs
    """
    from prefect.utilities.ids import _id_rng
    _id_rng.seed(config.general.get('id_seed') or random.getrandbits(128))


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

    for env_var in os.environ:
        if not env_var.startswith(ENV_VAR_PREFIX):
            continue
        sections = env_var.lower().split('__')[1:]
        if not sections:
            continue
        config_section = config
        # recurse to the last section
        for section in sections[:-1]:
            config_section = config_section.setdefault(section, {})
        # apply the env var value
        config_section[sections[-1]] = expand(os.getenv(env_var))

    if existing_config is not None:
        config = merge_dicts(existing_config, config)

    return dict_to_dotdict(config)


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

configure_ids()
configure_logging(logger_name='Prefect')
