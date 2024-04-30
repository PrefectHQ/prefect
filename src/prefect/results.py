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

from typing_extensions import ParamSpec, Self

import prefect
from prefect._internal.pydantic import HAS_PYDANTIC_V2
from prefect.blocks.core import Block
from prefect.client.utilities import inject_client
from prefect.exceptions import MissingResult
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

if HAS_PYDANTIC_V2:
    import pydantic.v1 as pydantic

else:
    import pydantic


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


@sync_compatible
async def get_default_result_storage() -> ResultStorage:
    """
    Generate a default file system for result storage.
    """
    return (
        await Block.load(PREFECT_DEFAULT_RESULT_STORAGE_BLOCK.value())
        if PREFECT_DEFAULT_RESULT_STORAGE_BLOCK.value() is not None
        else LocalFileSystem(basepath=PREFECT_LOCAL_STORAGE_PATH.value())
    )


_default_task_scheduling_storages: Dict[Tuple[str, str], WritableFileSystem] = {}


async def get_or_create_default_task_scheduling_storage() -> ResultStorage:
    """
    Generate a default file system for autonomous task parameter/result storage.
    """
    default_storage_name, storage_path = cache_key = (
        PREFECT_TASK_SCHEDULING_DEFAULT_STORAGE_BLOCK.value(),
        PREFECT_LOCAL_STORAGE_PATH.value(),
    )

    async def get_storage():
        try:
            return await Block.load(default_storage_name)
        except ValueError as e:
            if "Unable to find" not in str(e):
                raise e

        block_type_slug, name = default_storage_name.split("/")
        if block_type_slug == "local-file-system":
            block = LocalFileSystem(basepath=storage_path)
        else:
            raise Exception(
                "The default task storage block does not exist, but it is of type "
                f"'{block_type_slug}' which cannot be created implicitly.  Please create "
                "the block manually."
            )

        try:
            await block.save(name, overwrite=False)
            return block
        except ValueError as e:
            if "already in use" not in str(e):
                raise e

        return await Block.load(default_storage_name)

    try:
        return _default_task_scheduling_storages[cache_key]
    except KeyError:
        storage = await get_storage()
        _default_task_scheduling_storages[cache_key] = storage
        return storage


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


def _format_user_supplied_storage_key(key):
    # Note here we are pinning to task runs since flow runs do not support storage keys
    # yet; we'll need to split logic in the future or have two separate functions
    runtime_vars = {key: getattr(prefect.runtime, key) for key in dir(prefect.runtime)}
    return key.format(**runtime_vars, parameters=prefect.runtime.task_run.parameters)


class ResultFactory(pydantic.BaseModel):
    """
    A utility to generate `Result` types.
    """

    persist_result: bool
    cache_result_in_memory: bool
    serializer: Serializer
    storage_block_id: Optional[uuid.UUID]
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
        kwargs.setdefault("result_storage", await get_default_result_storage())
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
        from prefect.context import FlowRunContext

        ctx = FlowRunContext.get()

        if ctx and ctx.autonomous_task_run:
            return await cls.from_autonomous_task(task, client=client)

        return await cls._from_task(task, get_default_result_storage, client=client)

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
    async def create_result(self, obj: R) -> Union[R, "BaseResult[R]"]:
        """
        Create a result type for the given object.

        If persistence is disabled, the object is wrapped in an `UnpersistedResult` and
        returned.

        If persistence is enabled:
        - Bool and null types are converted into `LiteralResult`.
        - Other types are serialized, persisted to storage, and a reference is returned.
        """
        # Null objects are "cached" in memory at no cost
        should_cache_object = self.cache_result_in_memory or obj is None

        if not self.persist_result:
            return await UnpersistedResult.create(obj, cache_object=should_cache_object)

        if type(obj) in LITERAL_TYPES:
            return await LiteralResult.create(obj)

        return await PersistedResult.create(
            obj,
            storage_block=self.storage_block,
            storage_block_id=self.storage_block_id,
            storage_key_fn=self.storage_key_fn,
            serializer=self.serializer,
            cache_object=should_cache_object,
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
        blob = PersistedResultBlob.parse_raw(
            await self.storage_block.read_path(f"parameters/{identifier}")
        )
        return self.serializer.loads(blob.data)


@register_base_type
class BaseResult(pydantic.BaseModel, abc.ABC, Generic[R]):
    type: str
    artifact_type: Optional[str]
    artifact_description: Optional[str]

    def __init__(self, **data: Any) -> None:
        type_string = get_dispatch_key(self) if type(self) != BaseResult else "__base__"
        data.setdefault("type", type_string)
        super().__init__(**data)

    def __new__(cls: Type[Self], **kwargs) -> Self:
        if "type" in kwargs:
            try:
                subcls = lookup_type(cls, dispatch_key=kwargs["type"])
            except KeyError as exc:
                raise pydantic.ValidationError(errors=[exc], model=cls)
            return super().__new__(subcls)
        else:
            return super().__new__(cls)

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

    @classmethod
    def __dispatch_key__(cls, **kwargs):
        return cls.__fields__.get("type").get_default()


class UnpersistedResult(BaseResult):
    """
    Result type for results that are not persisted outside of local memory.
    """

    type = "unpersisted"

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
                f"Unsupported type {type(obj).__name__!r} for result literal. Expected"
                f" one of: {', '.join(type_.__name__ for type_ in LITERAL_TYPES)}"
            )

        description = f"Result with value `{obj}` persisted to Prefect."
        return cls(value=obj, artifact_type="result", artifact_description=description)


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
    async def get(self, client: "PrefectClient") -> R:
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
    async def _read_blob(self, client: "PrefectClient") -> "PersistedResultBlob":
        assert (
            self.storage_block_id is not None
        ), "Unexpected storage block ID. Was it persisted?"
        block_document = await client.read_block_document(self.storage_block_id)
        storage_block: ReadableFileSystem = Block._from_block_document(block_document)
        content = await storage_block.read_path(self.storage_key)
        blob = PersistedResultBlob.parse_raw(content)
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
    ) -> "PersistedResult[R]":
        """
        Create a new result reference from a user's object.

        The object will be serialized and written to the storage block under a unique
        key. It will then be cached on the returned result.
        """
        assert (
            storage_block_id is not None
        ), "Unexpected storage block ID. Was it persisted?"
        data = serializer.dumps(obj)
        blob = PersistedResultBlob(serializer=serializer, data=data)

        key = storage_key_fn()
        if not isinstance(key, str):
            raise TypeError(
                f"Expected type 'str' for result storage key; got value {key!r}"
            )

        await storage_block.write_path(key, content=blob.to_bytes())

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


class UnknownResult(BaseResult):
    """
    Result type for unknown results. Typically used to represent the result
    of tasks that were forced from a failure state into a completed state.

    The value for this result is always None and is not persisted to external
    result storage, but orchestration treats the result the same as persisted
    results when determining orchestration rules, such as whether to rerun a
    completed task.
    """

    type = "unknown"
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
