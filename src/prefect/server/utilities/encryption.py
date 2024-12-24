"""
Encryption utilities
"""

import json
import os
from collections.abc import Mapping
from typing import Any

from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server import schemas


async def _get_fernet_encryption(session: AsyncSession) -> Fernet:
    from prefect.server.models import configuration

    environment_key = os.getenv(
        "PREFECT_SERVER_ENCRYPTION_KEY",
        # Deprecated. Use the `PREFECT_SERVER_ENCRYPTION_KEY` instead.
        os.getenv("ORION_ENCRYPTION_KEY"),
    )
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


async def encrypt_fernet(session: AsyncSession, data: Mapping[str, Any]) -> str:
    fernet = await _get_fernet_encryption(session)
    byte_blob = json.dumps(data).encode()
    return fernet.encrypt(byte_blob).decode()


async def decrypt_fernet(session: AsyncSession, data: str) -> dict[str, Any]:
    fernet = await _get_fernet_encryption(session)
    byte_blob = data.encode()
    return json.loads(fernet.decrypt(byte_blob).decode())
