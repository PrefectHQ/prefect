import abc
import uuid
from functools import partial
from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Callable,
    Dict,
    Generic,
    Optional,
    Tuple,
    Type,
    TypeVar,
    Union,
)
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, ValidationError
from pydantic_core import PydanticUndefinedType
from pydantic_extra_types.pendulum_dt import DateTime
from typing_extensions import ParamSpec, Self

import prefect
from prefect.blocks.core import Block
from prefect.client.utilities import inject_client
from prefect.exceptions import MissingResult, ObjectAlreadyExists
from prefect.filesystems import (
    LocalFileSystem,
    ReadableFileSystem,
    WritableFileSystem,
)
from prefect.logging import get_logger
from prefect.serializers import Serializer
from prefect.settings import (
    PREFECT_DEFAULT_RESULT_STORAGE_BLOCK,
    PREFECT_LOCAL_STORAGE_PATH,
    PREFECT_RESULTS_DEFAULT_SERIALIZER,
    PREFECT_RESULTS_PERSIST_BY_DEFAULT,
    PREFECT_TASK_SCHEDULING_DEFAULT_STORAGE_BLOCK,
)
from prefect.utilities.annotations import NotSet
from prefect.utilities.asyncutils import sync_compatible
from prefect.utilities.pydantic import get_dispatch_key, lookup_type, register_base_type

if TYPE_CHECKING:
    from prefect import Flow, Task
    from prefect.client.orchestration import PrefectClient


ResultStorage = Union[WritableFileSystem, str]
ResultSerializer = Union[Serializer, str]
LITERAL_TYPES = {type(None), bool, UUID}


def DEFAULT_STORAGE_KEY_FN():
    return uuid.uuid4().hex


logger = get_logger("results")
P = ParamSpec("P")
R = TypeVar("R")

_default_storages: Dict[Tuple[str, str], WritableFileSystem] = {}


async def _get_or_create_default_storage(block_document_slug: str) -> ResultStorage:
    """
    Generate a default file system for storage.
    """
    default_storage_name, storage_path = cache_key = (
        block_document_slug,
        PREFECT_LOCAL_STORAGE_PATH.value(),
    )

    async def get_storage() -> WritableFileSystem:
        try:
            return await Block.load(default_storage_name)
        except ValueError as e:
            if "Unable to find" not in str(e):
                raise e

        block_type_slug, name = default_storage_name.split("/")
        if block_type_slug == "local-file-system":
            block = LocalFileSystem(basepath=storage_path)
        else:
            raise ValueError(
                "The default storage block does not exist, but it is of type "
                f"'{block_type_slug}' which cannot be created implicitly.  Please create "
                "the block manually."
            )

        try:
            await block.save(name, overwrite=False)
        except ValueError as e:
            if "already in use" not in str(e):
                raise e
        except ObjectAlreadyExists:
            # Another client created the block before we reached this line
            block = await Block.load(default_storage_name)

        return block

    try:
        return _default_storages[cache_key]
    except KeyError:
        storage = await get_storage()
        _default_storages[cache_key] = storage
        return storage


@sync_compatible
async def get_or_create_default_result_storage() -> ResultStorage:
    """
    Generate a default file system for result storage.
    """
    return await _get_or_create_default_storage(
        PREFECT_DEFAULT_RESULT_STORAGE_BLOCK.value()
    )


async def get_or_create_default_task_scheduling_storage() -> ResultStorage:
    """
    Generate a default file system for background task parameter/result storage.
    """
    return await _get_or_create_default_storage(
        PREFECT_TASK_SCHEDULING_DEFAULT_STORAGE_BLOCK.value()
    )


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
    if flow and flow.retries:
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


def _format_user_supplied_storage_key(key: str) -> str:
    # Note here we are pinning to task runs since flow runs do not support storage keys
    # yet; we'll need to split logic in the future or have two separate functions
    runtime_vars = {key: getattr(prefect.runtime, key) for key in dir(prefect.runtime)}
    return key.format(**runtime_vars, parameters=prefect.runtime.task_run.parameters)


class ResultFactory(BaseModel):
    """
    A utility to generate `Result` types.
    """

    persist_result: bool
    cache_result_in_memory: bool
    serializer: Serializer
    storage_block_id: Optional[uuid.UUID] = None
    storage_block: WritableFileSystem
    storage_key_fn: Callable[[], str]

    @classmethod
    @inject_client
    async def default_factory(cls, client: "PrefectClient" = None, **kwargs):
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
        kwargs.setdefault(
            "result_storage", await get_or_create_default_result_storage()
        )
        kwargs.setdefault("result_serializer", get_default_result_serializer())
        kwargs.setdefault("persist_result", get_default_persist_setting())
        kwargs.setdefault("cache_result_in_memory", True)
        kwargs.setdefault("storage_key_fn", DEFAULT_STORAGE_KEY_FN)

        return await cls.from_settings(**kwargs, client=client)

    @classmethod
    @inject_client
    async def from_flow(
        cls: Type[Self], flow: "Flow", client: "PrefectClient" = None
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
                    # !! Child flows persist their result by default if the it or the
                    #    parent flow uses a feature that requires it
                    else (
                        flow_features_require_result_persistence(flow)
                        or flow_features_require_child_result_persistence(ctx.flow)
                        or get_default_persist_setting()
                    )
                ),
                cache_result_in_memory=flow.cache_result_in_memory,
                storage_key_fn=DEFAULT_STORAGE_KEY_FN,
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
                    # !! Flows persist their result by default if uses a feature that
                    #    requires it
                    else (
                        flow_features_require_result_persistence(flow)
                        or get_default_persist_setting()
                    )
                ),
                cache_result_in_memory=flow.cache_result_in_memory,
                storage_key_fn=DEFAULT_STORAGE_KEY_FN,
            )

    @classmethod
    @inject_client
    async def from_task(
        cls: Type[Self], task: "Task", client: "PrefectClient" = None
    ) -> Self:
        """
        Create a new result factory for a task.
        """
        return await cls._from_task(
            task, get_or_create_default_result_storage, client=client
        )

    @classmethod
    @inject_client
    async def from_autonomous_task(
        cls: Type[Self], task: "Task[P, R]", client: "PrefectClient" = None
    ) -> Self:
        """
        Create a new result factory for an autonomous task.
        """
        return await cls._from_task(
            task, get_or_create_default_task_scheduling_storage, client=client
        )

    @classmethod
    @inject_client
    async def _from_task(
        cls: Type[Self],
        task: "Task",
        default_storage_getter: Callable[[], Awaitable[ResultStorage]],
        client: "PrefectClient" = None,
    ) -> Self:
        from prefect.context import FlowRunContext

        ctx = FlowRunContext.get()

        result_storage = task.result_storage or (
            ctx.result_factory.storage_block
            if ctx and ctx.result_factory
            else await default_storage_getter()
        )
        result_serializer = task.result_serializer or (
            ctx.result_factory.serializer
            if ctx and ctx.result_factory
            else get_default_result_serializer()
        )
        persist_result = (
            task.persist_result
            if task.persist_result is not None
            # !! Tasks persist their result by default if their parent flow uses a
            #    feature that requires it or the task uses a feature that requires it
            else (
                (
                    flow_features_require_child_result_persistence(ctx.flow)
                    if ctx
                    else False
                )
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
            storage_key_fn=(
                partial(_format_user_supplied_storage_key, task.result_storage_key)
                if task.result_storage_key is not None
                else DEFAULT_STORAGE_KEY_FN
            ),
        )

    @classmethod
    @inject_client
    async def from_settings(
        cls: Type[Self],
        result_storage: ResultStorage,
        result_serializer: ResultSerializer,
        persist_result: bool,
        cache_result_in_memory: bool,
        storage_key_fn: Callable[[], str],
        client: "PrefectClient",
    ) -> Self:
        storage_block_id, storage_block = await cls.resolve_storage_block(
            result_storage, client=client, persist_result=persist_result
        )
        serializer = cls.resolve_serializer(result_serializer)

        return cls(
            storage_block=storage_block,
            storage_block_id=storage_block_id,
            serializer=serializer,
            persist_result=persist_result,
            cache_result_in_memory=cache_result_in_memory,
            storage_key_fn=storage_key_fn,
        )

    @staticmethod
    async def resolve_storage_block(
        result_storage: ResultStorage,
        client: "PrefectClient",
        persist_result: bool = True,
    ) -> Tuple[Optional[uuid.UUID], WritableFileSystem]:
        """
        Resolve one of the valid `ResultStorage` input types into a saved block
        document id and an instance of the block.
        """
        if isinstance(result_storage, Block):
            storage_block = result_storage

            if storage_block._block_document_id is not None:
                # Avoid saving the block if it already has an identifier assigned
                storage_block_id = storage_block._block_document_id
            else:
                if persist_result:
                    # TODO: Overwrite is true to avoid issues where the save collides with
                    # a previously saved document with a matching hash
                    storage_block_id = await storage_block._save(
                        is_anonymous=True, overwrite=True, client=client
                    )
                else:
                    # a None-type UUID on unpersisted storage should not matter
                    # since the ID is generated on the server
                    storage_block_id = None
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
    async def create_result(
        self,
        obj: R,
        key: Optional[str] = None,
        expiration: Optional[DateTime] = None,
        defer_persistence: bool = False,
    ) -> Union[R, "BaseResult[R]"]:
        """
        Create a result type for the given object.

        If persistence is disabled, the object is wrapped in an `UnpersistedResult` and
        returned.

        If persistence is enabled the object is serialized, persisted to storage, and a reference is returned.
        """
        # Null objects are "cached" in memory at no cost
        should_cache_object = self.cache_result_in_memory or obj is None

        if not self.persist_result:
            return await UnpersistedResult.create(obj, cache_object=should_cache_object)

        if key:

            def key_fn():
                return key

            storage_key_fn = key_fn
        else:
            storage_key_fn = self.storage_key_fn

        return await PersistedResult.create(
            obj,
            storage_block=self.storage_block,
            storage_block_id=self.storage_block_id,
            storage_key_fn=storage_key_fn,
            serializer=self.serializer,
            cache_object=should_cache_object,
            expiration=expiration,
            defer_persistence=defer_persistence,
        )

    @sync_compatible
    async def store_parameters(self, identifier: UUID, parameters: Dict[str, Any]):
        assert (
            self.storage_block_id is not None
        ), "Unexpected storage block ID. Was it persisted?"
        data = self.serializer.dumps(parameters)
        blob = PersistedResultBlob(serializer=self.serializer, data=data)
        await self.storage_block.write_path(
            f"parameters/{identifier}", content=blob.to_bytes()
        )

    @sync_compatible
    async def read_parameters(self, identifier: UUID) -> Dict[str, Any]:
        assert (
            self.storage_block_id is not None
        ), "Unexpected storage block ID. Was it persisted?"
        blob = PersistedResultBlob.model_validate_json(
            await self.storage_block.read_path(f"parameters/{identifier}")
        )
        return self.serializer.loads(blob.data)


@register_base_type
class BaseResult(BaseModel, abc.ABC, Generic[R]):
    model_config = ConfigDict(extra="forbid")

    type: str
    artifact_type: Optional[str] = None
    artifact_description: Optional[str] = None

    def __init__(self, **data: Any) -> None:
        type_string = get_dispatch_key(self) if type(self) != BaseResult else "__base__"
        data.setdefault("type", type_string)
        super().__init__(**data)

    def __new__(cls: Type[Self], **kwargs) -> Self:
        if "type" in kwargs:
            try:
                subcls = lookup_type(cls, dispatch_key=kwargs["type"])
            except KeyError as exc:
                raise ValidationError(errors=[exc], model=cls)
            return super().__new__(subcls)
        else:
            return super().__new__(cls)

    _cache: Any = PrivateAttr(NotSet)

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

    @classmethod
    def __dispatch_key__(cls, **kwargs):
        default = cls.model_fields.get("type").get_default()
        return cls.__name__ if isinstance(default, PydanticUndefinedType) else default


class UnpersistedResult(BaseResult):
    """
    Result type for results that are not persisted outside of local memory.
    """

    type: str = "unpersisted"

    @sync_compatible
    async def get(self) -> R:
        if self.has_cached_object():
            return self._cache

        raise MissingResult("The result was not persisted and is no longer available.")

    @classmethod
    @sync_compatible
    async def create(
        cls: "Type[UnpersistedResult]",
        obj: R,
        cache_object: bool = True,
    ) -> "UnpersistedResult[R]":
        description = f"Unpersisted result of type `{type(obj).__name__}`"
        result = cls(
            artifact_type="result",
            artifact_description=description,
        )
        # Only store the object in local memory, it will not be sent to the API
        if cache_object:
            result._cache_object(obj)
        return result


class PersistedResult(BaseResult):
    """
    Result type which stores a reference to a persisted result.

    When created, the user's object is serialized and stored. The format for the content
    is defined by `PersistedResultBlob`. This reference contains metadata necessary for retrieval
    of the object, such as a reference to the storage block and the key where the
    content was written.
    """

    type: str = "reference"

    serializer_type: str
    storage_block_id: uuid.UUID
    storage_key: str
    expiration: Optional[DateTime] = None

    _should_cache_object: bool = PrivateAttr(default=True)
    _persisted: bool = PrivateAttr(default=False)
    _storage_block: WritableFileSystem = PrivateAttr(default=None)
    _serializer: Serializer = PrivateAttr(default=None)

    def _cache_object(
        self,
        obj: Any,
        storage_block: WritableFileSystem = None,
        serializer: Serializer = None,
    ) -> None:
        self._cache = obj
        self._storage_block = storage_block
        self._serializer = serializer

    @sync_compatible
    @inject_client
    async def get(self, client: "PrefectClient") -> R:
        """
        Retrieve the data and deserialize it into the original object.
        """

        if self.has_cached_object():
            return self._cache

        blob = await self._read_blob(client=client)
        obj = blob.load()
        self.expiration = blob.expiration

        if self._should_cache_object:
            self._cache_object(obj)

        return obj

    @inject_client
    async def _read_blob(self, client: "PrefectClient") -> "PersistedResultBlob":
        assert (
            self.storage_block_id is not None
        ), "Unexpected storage block ID. Was it persisted?"
        block_document = await client.read_block_document(self.storage_block_id)
        storage_block: ReadableFileSystem = Block._from_block_document(block_document)
        content = await storage_block.read_path(self.storage_key)
        blob = PersistedResultBlob.model_validate_json(content)
        return blob

    @staticmethod
    def _infer_path(storage_block, key) -> str:
        """
        Attempts to infer a path associated with a storage block key, this method will
        defer to the block in the future
        """

        if hasattr(storage_block, "_resolve_path"):
            return storage_block._resolve_path(key)
        if hasattr(storage_block, "_remote_file_system"):
            return storage_block._remote_file_system._resolve_path(key)

    @sync_compatible
    @inject_client
    async def write(self, obj: R = NotSet, client: "PrefectClient" = None) -> None:
        """
        Write the result to the storage block.
        """

        if self._persisted:
            # don't double write or overwrite
            return

        # load objects from a cache

        # first the object itself
        if obj is NotSet and not self.has_cached_object():
            raise ValueError("Cannot write a result that has no object cached.")
        obj = obj if obj is not NotSet else self._cache

        # next, the storage block
        storage_block = self._storage_block
        if storage_block is None:
            block_document = await client.read_block_document(self.storage_block_id)
            storage_block = Block._from_block_document(block_document)

        # finally, the serializer
        serializer = self._serializer
        if serializer is None:
            # this could error if the serializer requires kwargs
            serializer = Serializer(type=self.serializer_type)

        data = serializer.dumps(obj)
        blob = PersistedResultBlob(
            serializer=serializer, data=data, expiration=self.expiration
        )
        await storage_block.write_path(self.storage_key, content=blob.to_bytes())
        self._persisted = True

        if not self._should_cache_object:
            self._cache = NotSet

    @classmethod
    @sync_compatible
    async def create(
        cls: "Type[PersistedResult]",
        obj: R,
        storage_block: WritableFileSystem,
        storage_block_id: uuid.UUID,
        storage_key_fn: Callable[[], str],
        serializer: Serializer,
        cache_object: bool = True,
        expiration: Optional[DateTime] = None,
        defer_persistence: bool = False,
    ) -> "PersistedResult[R]":
        """
        Create a new result reference from a user's object.

        The object will be serialized and written to the storage block under a unique
        key. It will then be cached on the returned result.
        """
        assert (
            storage_block_id is not None
        ), "Unexpected storage block ID. Was it saved?"

        key = storage_key_fn()
        if not isinstance(key, str):
            raise TypeError(
                f"Expected type 'str' for result storage key; got value {key!r}"
            )
        description = f"Result of type `{type(obj).__name__}`"
        uri = cls._infer_path(storage_block, key)
        if uri:
            if isinstance(storage_block, LocalFileSystem):
                description += f" persisted to: `{uri}`"
            else:
                description += f" persisted to [{uri}]({uri})."
        else:
            description += f" persisted with storage block `{storage_block_id}`."

        result = cls(
            serializer_type=serializer.type,
            storage_block_id=storage_block_id,
            storage_key=key,
            artifact_type="result",
            artifact_description=description,
            expiration=expiration,
        )

        if cache_object and not defer_persistence:
            # Attach the object to the result so it's available without deserialization
            result._cache_object(
                obj, storage_block=storage_block, serializer=serializer
            )

        object.__setattr__(result, "_should_cache_object", cache_object)

        if not defer_persistence:
            await result.write(obj=obj)
        else:
            # we must cache temporarily to allow for writing later
            # the cache will be removed on write
            result._cache_object(
                obj, storage_block=storage_block, serializer=serializer
            )

        return result


class PersistedResultBlob(BaseModel):
    """
    The format of the content stored by a persisted result.

    Typically, this is written to a file as bytes.
    """

    serializer: Serializer
    data: bytes
    prefect_version: str = Field(default=prefect.__version__)
    expiration: Optional[DateTime] = None

    def load(self) -> Any:
        return self.serializer.loads(self.data)

    def to_bytes(self) -> bytes:
        return self.model_dump_json(serialize_as_any=True).encode()


class UnknownResult(BaseResult):
    """
    Result type for unknown results. Typically used to represent the result
    of tasks that were forced from a failure state into a completed state.

    The value for this result is always None and is not persisted to external
    result storage, but orchestration treats the result the same as persisted
    results when determining orchestration rules, such as whether to rerun a
    completed task.
    """

    type: str = "unknown"
    value: None

    def has_cached_object(self) -> bool:
        # This result type always has the object cached in memory
        return True

    @sync_compatible
    async def get(self) -> R:
        return self.value

    @classmethod
    @sync_compatible
    async def create(
        cls: "Type[UnknownResult]",
        obj: R = None,
    ) -> "UnknownResult[R]":
        if obj is not None:
            raise TypeError(
                f"Unsupported type {type(obj).__name__!r} for unknown result. "
                "Only None is supported."
            )

        description = "Unknown result persisted to Prefect."
        return cls(value=obj, artifact_type="result", artifact_description=description)
