import os
import tempfile
import uuid
from cryptography.fernet import Fernet
from prefect import configuration


template = b"""
    [interpolation]

    password1 = <<SECRET>>
    password2 = <<SECRET>>

    uuid1 = <<UUID>>
    uuid2 = <<UUID>>

    fernet1 = <<FERNET KEY>>
    fernet2 = <<FERNET KEY>>
    """


def test_substitution():
    with tempfile.NamedTemporaryFile() as default_config:
        default_config.write(template)
        default_config.seek(0)

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, str(uuid.uuid4()))
            configuration.create_user_config(path, source=default_config.name)
            config = configuration.load_config_file(path)

    assert len(config.interpolation.password1) == 32
    assert len(config.interpolation.password2) == 32
    assert config.interpolation.password1 != config.interpolation.password2

    assert uuid.UUID(config.interpolation.uuid1)
    assert uuid.UUID(config.interpolation.uuid2)
    assert config.interpolation.uuid1 != config.interpolation.uuid2

    assert Fernet(config.interpolation.fernet1)
    assert Fernet(config.interpolation.fernet2)
    assert config.interpolation.fernet1 != config.interpolation.fernet2
