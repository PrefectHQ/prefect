"""
Encryption utilities
"""
import json
import os

from cryptography.fernet import Fernet

from prefect.orion import schemas


async def get_fernet_encryption(session):
    from prefect.orion.models import configuration

    environment_key = os.getenv("ORION_ENCRYPTION_KEY")
    if environment_key:
        return Fernet(environment_key.encode())

    configured_key = await configuration.read_configuration(session, "ENCRYPTION_KEY")

    if configured_key is None:
        encryption_key = Fernet.generate_key()
        configured_key = schemas.core.Configuration(
            key="ENCRYPTION_KEY", value={"fernet_key": encryption_key.decode()}
        )
        await configuration.write_configuration(session, configured_key)
    else:
        encryption_key = configured_key.value["fernet_key"].encode()
    return Fernet(encryption_key)


async def encrypt_fernet(session, data: dict):
    fernet = await get_fernet_encryption(session)
    byte_blob = json.dumps(data).encode()
    return fernet.encrypt(byte_blob).decode()


async def decrypt_fernet(session, data: dict):
    fernet = await get_fernet_encryption(session)
    byte_blob = data.encode()
    return json.loads(fernet.decrypt(byte_blob).decode())
