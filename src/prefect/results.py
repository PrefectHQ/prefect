import uuid
from typing import TYPE_CHECKING, Any, Tuple, Type, Union

import pydantic
from typing_extensions import Self

from prefect.blocks.core import Block
from prefect.client import OrionClient
from prefect.client.orion import inject_client
from prefect.deprecated.data_documents import DataDocument
from prefect.exceptions import MissingContextError
from prefect.filesystems import LocalFileSystem, WritableFileSystem
from prefect.serializers import Serializer
from prefect.settings import (
    PREFECT_LOCAL_STORAGE_PATH,
    PREFECT_RESULTS_DEFAULT_SERIALIZER,
)

ResultStorage = Union[WritableFileSystem, str]
ResultSerializer = Union[Serializer, str]
if TYPE_CHECKING:
    from prefect import Flow, Task


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


## ----


def get_default_result_storage() -> ResultStorage:
    """
    Generate a default file system for result storage.
    """
    return LocalFileSystem(basepath=PREFECT_LOCAL_STORAGE_PATH.value())


def get_default_result_serializer() -> ResultSerializer:
    """
    Generate a default file system for result storage.
    """
    return PREFECT_RESULTS_DEFAULT_SERIALIZER.value()


def flow_features_require_child_result_persistence(flow: "Flow") -> bool:
    """
    Returns `True` if the given flow uses features that require child flow and task
    runs to persist their results.
    """
    if flow.retries:
        return True
    return False


def task_features_require_result_persistence(task: "Task") -> bool:
    """
    Returns `True` if the given task uses features that require its result to be
    persisted.
    """
    if task.cache_key_fn:
        return True
    return False


class ResultFactory(pydantic.BaseModel):
    """
    A utility to generate `Result` types.
    """

    persist_result: bool
    serializer: Serializer
    storage_block_id: uuid.UUID
    storage_block: WritableFileSystem

    async def create_result(self, obj: Any) -> _Result:
        """
        Create a result from a user's return value.
        """

    @classmethod
    @inject_client
    async def from_flow(cls: Type[Self], flow: "Flow", client: OrionClient) -> Self:
        """
        Create a new result factory for a flow.
        """
        from prefect.context import FlowRunContext

        ctx = FlowRunContext.get()
        if ctx:
            # This is a child flow run
            result_storage = flow.result_storage or ctx.result_factory.storage_block
            result_serializer = flow.result_serializer or ctx.result_factory.serializer
            persist_result = (
                flow.persist_result
                if flow.persist_result is not None
                else
                # !! Child flows persist their result by default if the parent flow
                #    uses a feature that requires it
                flow_features_require_child_result_persistence(ctx.flow)
            )
        else:
            result_storage = flow.result_storage or get_default_result_storage()
            result_serializer = (
                flow.result_serializer or get_default_result_serializer()
            )
            persist_result = (
                flow.persist_result
                if flow.persist_result is not None
                # !! Root flows do not persist their result by default ever at this time
                else False
            )

        return await cls.from_settings(
            result_storage=result_storage,
            result_serializer=result_serializer,
            persist_result=persist_result,
            client=client,
        )

    @classmethod
    @inject_client
    async def from_task(cls: Type[Self], task: "Task", client: OrionClient) -> Self:
        """
        Create a new result factory for a task.
        """
        from prefect.context import FlowRunContext

        ctx = FlowRunContext.get()
        if not ctx:
            raise MissingContextError(
                "A flow run context is required to create a result factory for a task."
            )

        result_storage = task.result_storage or ctx.result_factory.storage_block
        result_serializer = task.result_serializer or ctx.result_factory.serializer
        persist_result = (
            task.persist_result
            if task.persist_result is not None
            else
            # !! Tasks persist their result by default if their parent flow uses a
            #    feature that requires it or the task uses a feature that requires it
            (
                flow_features_require_child_result_persistence(ctx.flow)
                or task_features_require_result_persistence(task)
            )
        )

        return await cls.from_settings(
            result_storage=result_storage,
            result_serializer=result_serializer,
            persist_result=persist_result,
            client=client,
        )

    @classmethod
    @inject_client
    async def from_settings(
        cls: Type[Self],
        result_storage: ResultStorage,
        result_serializer: ResultSerializer,
        persist_result: bool,
        client: OrionClient,
    ) -> Self:
        storage_block_id, storage_block = await cls.resolve_storage_block(
            result_storage, client=client
        )
        serializer = cls.resolve_serializer(result_serializer)

        return cls(
            storage_block=storage_block,
            storage_block_id=storage_block_id,
            serializer=serializer,
            persist_result=persist_result,
        )

    @staticmethod
    async def resolve_storage_block(
        result_storage: ResultStorage, client: OrionClient
    ) -> Tuple[uuid.UUID, WritableFileSystem]:
        """
        Resolve one of the valid `ResultStorage` input types into a saved block
        document id and an instance of the block.
        """
        if isinstance(result_storage, Block):
            storage_block = result_storage
            storage_block_id = (
                # Avoid saving the block if it already has an identifier assigned
                storage_block._block_document_id
                # TODO: Overwrite is true to avoid issues where the save collides with
                #       a previously saved document with a matching hash
                or await storage_block._save(is_anonymous=True, overwrite=True)
            )
        elif isinstance(result_storage, str):
            storage_block = await Block.load(result_storage, client=client)
            storage_block_id = storage_block._block_document_id
            assert storage_block_id is not None, "Loaded storage blocks must have ids"
        else:
            raise TypeError(
                "Result storage must be one of the following types: 'UUID', 'Block', "
                f"'str'. Got unsupported type {type(result_storage).__name__!r}."
            )

        return storage_block_id, storage_block

    @staticmethod
    def resolve_serializer(serializer: ResultSerializer) -> Serializer:
        """
        Resolve one of the valid `ResultSerializer` input types into a serializer
        instance.
        """
        if isinstance(serializer, Serializer):
            return serializer
        elif isinstance(serializer, str):
            return Serializer(type=serializer)
        else:
            raise TypeError(
                "Result serializer must be one of the following types: 'Serializer', "
                f"'str'. Got unsupported type {type(serializer).__name__!r}."
            )
