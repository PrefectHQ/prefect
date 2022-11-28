import abc
import uuid
from typing import TYPE_CHECKING, Any, Generic, Tuple, Type, TypeVar, Union

import pydantic
from typing_extensions import Self

import prefect
from prefect.blocks.core import Block
from prefect.client.utilities import inject_client
from prefect.exceptions import MissingContextError
from prefect.filesystems import LocalFileSystem, ReadableFileSystem, WritableFileSystem
from prefect.logging import get_logger
from prefect.serializers import Serializer
from prefect.settings import (
    PREFECT_LOCAL_STORAGE_PATH,
    PREFECT_RESULTS_DEFAULT_SERIALIZER,
    PREFECT_RESULTS_PERSIST_BY_DEFAULT,
)
from prefect.utilities.annotations import NotSet
from prefect.utilities.asyncutils import sync_compatible
from prefect.utilities.pydantic import add_type_dispatch

if TYPE_CHECKING:
    from prefect import Flow, Task
    from prefect.client.orion import OrionClient


ResultStorage = Union[WritableFileSystem, str]
ResultSerializer = Union[Serializer, str]
LITERAL_TYPES = {type(None), bool}

logger = get_logger("results")

# from prefect.orion.schemas.states import State
R = TypeVar("R")


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


def get_default_persist_setting() -> bool:
    """
    Return the default option for result persistence (False).
    """
    return PREFECT_RESULTS_PERSIST_BY_DEFAULT.value()


def flow_features_require_result_persistence(flow: "Flow") -> bool:
    """
    Returns `True` if the given flow uses features that require its result to be
    persisted.
    """
    if not flow.cache_result_in_memory:
        return True
    return False


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
    if not task.cache_result_in_memory:
        return True
    return False


class ResultFactory(pydantic.BaseModel):
    """
    A utility to generate `Result` types.
    """

    persist_result: bool
    cache_result_in_memory: bool
    serializer: Serializer
    storage_block_id: uuid.UUID
    storage_block: WritableFileSystem

    @classmethod
    @inject_client
    async def default_factory(cls, client: "OrionClient" = None, **kwargs):
        """
        Create a new result factory with default options.

        Keyword arguments may be provided to override defaults. Null keys will be
        ignored.
        """
        # Remove any null keys so `setdefault` can do its magic
        for key, value in tuple(kwargs.items()):
            if value is None:
                kwargs.pop(key)

        # Apply defaults
        kwargs.setdefault("result_storage", get_default_result_storage())
        kwargs.setdefault("result_serializer", get_default_result_serializer())
        kwargs.setdefault("persist_result", get_default_persist_setting())
        kwargs.setdefault("cache_result_in_memory", True)

        return await cls.from_settings(**kwargs, client=client)

    @classmethod
    @inject_client
    async def from_flow(
        cls: Type[Self], flow: "Flow", client: "OrionClient" = None
    ) -> Self:
        """
        Create a new result factory for a flow.
        """
        from prefect.context import FlowRunContext

        ctx = FlowRunContext.get()
        if ctx:
            # This is a child flow run
            return await cls.from_settings(
                result_storage=flow.result_storage or ctx.result_factory.storage_block,
                result_serializer=flow.result_serializer
                or ctx.result_factory.serializer,
                persist_result=(
                    flow.persist_result
                    if flow.persist_result is not None
                    else
                    # !! Child flows persist their result by default if the it or the
                    #    parent flow uses a feature that requires it
                    (
                        flow_features_require_result_persistence(flow)
                        or flow_features_require_child_result_persistence(ctx.flow)
                        or get_default_persist_setting()
                    )
                ),
                cache_result_in_memory=flow.cache_result_in_memory,
                client=client,
            )
        else:
            # This is a root flow run
            # Pass the flow settings up to the default which will replace nulls with
            # our default options
            return await cls.default_factory(
                client=client,
                result_storage=flow.result_storage,
                result_serializer=flow.result_serializer,
                persist_result=(
                    flow.persist_result
                    if flow.persist_result is not None
                    else
                    # !! Flows persist their result by default if uses a feature that
                    #    requires it
                    (
                        flow_features_require_result_persistence(flow)
                        or get_default_persist_setting()
                    )
                ),
                cache_result_in_memory=flow.cache_result_in_memory,
            )

    @classmethod
    @inject_client
    async def from_task(
        cls: Type[Self], task: "Task", client: "OrionClient" = None
    ) -> Self:
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
                or get_default_persist_setting()
            )
        )
        cache_result_in_memory = task.cache_result_in_memory

        return await cls.from_settings(
            result_storage=result_storage,
            result_serializer=result_serializer,
            persist_result=persist_result,
            cache_result_in_memory=cache_result_in_memory,
            client=client,
        )

    @classmethod
    @inject_client
    async def from_settings(
        cls: Type[Self],
        result_storage: ResultStorage,
        result_serializer: ResultSerializer,
        persist_result: bool,
        cache_result_in_memory: bool,
        client: "OrionClient",
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
            cache_result_in_memory=cache_result_in_memory,
        )

    @staticmethod
    async def resolve_storage_block(
        result_storage: ResultStorage, client: "OrionClient"
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

    @sync_compatible
    async def create_result(self, obj: R) -> Union[R, "BaseResult[R]"]:
        """
        Create a result type for the given object.

        If persistence is disabled, the object is returned unaltered.

        Literal types are converted into `LiteralResult`.

        Other types are serialized, persisted to storage, and a reference is returned.
        """
        if obj is None:
            # Always write nulls as result types to distinguish from unpersisted results
            return await LiteralResult.create(None)

        if not self.persist_result:
            # Attach the object directly if persistence is disabled; it will be dropped
            # when sent to the API
            if self.cache_result_in_memory:
                return obj
            # Unless in-memory caching has been disabled, then this result will not be
            # available downstream
            else:
                return None

        if type(obj) in LITERAL_TYPES:
            return await LiteralResult.create(obj)

        return await PersistedResult.create(
            obj,
            storage_block=self.storage_block,
            storage_block_id=self.storage_block_id,
            serializer=self.serializer,
            cache_object=self.cache_result_in_memory,
        )


@add_type_dispatch
class BaseResult(pydantic.BaseModel, abc.ABC, Generic[R]):
    type: str

    _cache: Any = pydantic.PrivateAttr(NotSet)

    def _cache_object(self, obj: Any) -> None:
        self._cache = obj

    def has_cached_object(self) -> bool:
        return self._cache is not NotSet

    @abc.abstractmethod
    @sync_compatible
    async def get(self) -> R:
        ...

    @abc.abstractclassmethod
    @sync_compatible
    async def create(
        cls: "Type[BaseResult[R]]",
        obj: R,
        **kwargs: Any,
    ) -> "BaseResult[R]":
        ...

    class Config:
        extra = "forbid"


class LiteralResult(BaseResult):
    """
    Result type for literal values like `None`, `True`, `False`.

    These values are stored inline and JSON serialized when sent to the Prefect API.
    They are not persisted to external result storage.
    """

    type = "literal"
    value: Any

    def has_cached_object(self) -> bool:
        # This result type always has the object cached in memory
        return True

    @sync_compatible
    async def get(self) -> R:
        return self.value

    @classmethod
    @sync_compatible
    async def create(
        cls: "Type[LiteralResult]",
        obj: R,
    ) -> "LiteralResult[R]":
        if type(obj) not in LITERAL_TYPES:
            raise TypeError(
                f"Unsupported type {type(obj).__name__!r} for result literal. "
                f"Expected one of: {', '.join(type_.__name__ for type_ in LITERAL_TYPES)}"
            )

        return cls(value=obj)


class PersistedResult(BaseResult):
    """
    Result type which stores a reference to a persisted result.

    When created, the user's object is serialized and stored. The format for the content
    is defined by `PersistedResultBlob`. This reference contains metadata necessary for retrieval
    of the object, such as a reference to the storage block and the key where the
    content was written.
    """

    type = "reference"

    serializer_type: str
    storage_block_id: uuid.UUID
    storage_key: str

    _should_cache_object: bool = pydantic.PrivateAttr(default=True)

    @sync_compatible
    @inject_client
    async def get(self, client: "OrionClient") -> R:
        """
        Retrieve the data and deserialize it into the original object.
        """
        if self.has_cached_object():
            return self._cache

        blob = await self._read_blob(client=client)
        obj = blob.serializer.loads(blob.data)

        if self._should_cache_object:
            self._cache_object(obj)

        return obj

    @inject_client
    async def _read_blob(self, client: "OrionClient") -> "PersistedResultBlob":
        block_document = await client.read_block_document(self.storage_block_id)
        storage_block: ReadableFileSystem = Block._from_block_document(block_document)
        content = await storage_block.read_path(self.storage_key)
        blob = PersistedResultBlob.parse_raw(content)
        return blob

    @classmethod
    @sync_compatible
    async def create(
        cls: "Type[PersistedResult]",
        obj: R,
        storage_block: WritableFileSystem,
        storage_block_id: uuid.UUID,
        serializer: Serializer,
        cache_object: bool = True,
    ) -> "PersistedResult[R]":
        """
        Create a new result reference from a user's object.

        The object will be serialized and written to the storage block under a unique
        key. It will then be cached on the returned result.
        """
        data = serializer.dumps(obj)
        blob = PersistedResultBlob(serializer=serializer, data=data)

        key = uuid.uuid4().hex
        await storage_block.write_path(key, content=blob.to_bytes())

        result = cls(
            serializer_type=serializer.type,
            storage_block_id=storage_block_id,
            storage_key=key,
        )

        if cache_object:
            # Attach the object to the result so it's available without deserialization
            result._cache_object(obj)

        object.__setattr__(result, "_should_cache_object", cache_object)

        return result


class PersistedResultBlob(pydantic.BaseModel):
    """
    The format of the content stored by a persisted result.

    Typically, this is written to a file as bytes.
    """

    serializer: Serializer
    data: bytes
    prefect_version: str = pydantic.Field(default=prefect.__version__)

    def to_bytes(self) -> bytes:
        return self.json().encode()
