import pytest
import os
import tempfile
import uuid
from cryptography.fernet import Fernet
from prefect import configuration

template = b"""
    [general]
    x = 1
    y = "hi"

    [env_vars]
    path = "$PATH"

    [interpolation]
    x = "${interpolation.y}"
    y = 11
    z = "${interpolation.x}"

    [substitution]

    password1 = "<<SECRET>>"
    password2 = "<<SECRET>>"

    uuid1 = "<<UUID>>"
    uuid2 = "<<UUID>>"

    fernet1 = "<<FERNET KEY>>"
    fernet2 = "<<FERNET KEY>>"
    """


@pytest.fixture
def config():
    with tempfile.NamedTemporaryFile() as default_config:
        default_config.write(template)
        default_config.seek(0)

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, str(uuid.uuid4()))
            configuration.create_user_config(path, source=default_config.name)
            config = configuration.load_config_file(path)

    return config


def test_general(config):
    assert config.general.x == 1
    assert config.general.y == 'hi'


def test_substitution(config):

    assert len(config.substitution.password1) == 32
    assert len(config.substitution.password2) == 32
    assert config.substitution.password1 != config.substitution.password2

    assert uuid.UUID(config.substitution.uuid1)
    assert uuid.UUID(config.substitution.uuid2)
    assert config.substitution.uuid1 != config.substitution.uuid2

    assert Fernet(config.substitution.fernet1)
    assert Fernet(config.substitution.fernet2)
    assert config.substitution.fernet1 != config.substitution.fernet2


def test_env_var_expansion(config):
    assert config.env_vars.path == os.getenv('PATH')


def test_env_var_configuration():
    os.environ['PREFECT__ENV_VARS__TEST'] = 'test'
    assert config().env_vars.test == 'test'


def test_interpolation(config):
    assert config.interpolation.y == 11
    assert config.interpolation.x == config.interpolation.y
    assert config.interpolation.z == config.interpolation.y
