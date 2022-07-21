import uuid

import pydantic

from prefect.blocks.core import Block
from prefect.client import OrionClient, inject_client
from prefect.filesystems import WritableFileSystem
from prefect.orion.schemas.data import DataDocument


async def _persist_serialized_result(
    content: bytes, filesystem: WritableFileSystem
) -> DataDocument:
    key = uuid.uuid4().hex
    await filesystem.write_path(key, content)
    result = _Result(key=key, filesystem_document_id=filesystem._block_document_id)
    return DataDocument.encode("result", result)


@inject_client
async def _retrieve_serialized_result(
    document: DataDocument, client: OrionClient
) -> bytes:
    if document.encoding != "result":
        raise TypeError(
            f"Got unsupported data document encoding of {document.encoding!r}. "
            "Expected 'result'."
        )
    result = document.decode()
    filesystem_document = await client.read_block_document(
        result.filesystem_document_id
    )
    filesystem = Block._from_block_document(filesystem_document)
    return await filesystem.read_path(result.key)


async def _retrieve_result(state):
    serialized_result = await _retrieve_serialized_result(state.data)
    return DataDocument.parse_raw(serialized_result).decode()


class _Result(pydantic.BaseModel):
    key: str
    filesystem_document_id: uuid.UUID
