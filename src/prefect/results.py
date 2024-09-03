import abc
import inspect
import uuid
from functools import partial
from typing import (
    TYPE_CHECKING,
    Any,
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

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    ValidationError,
    model_serializer,
    model_validator,
)
from pydantic_core import PydanticUndefinedType
from pydantic_extra_types.pendulum_dt import DateTime
from typing_extensions import ParamSpec, Self

import prefect
from prefect.blocks.core import Block
from prefect.client.utilities import inject_client
from prefect.exceptions import MissingContextError, SerializationError
from prefect.filesystems import (
    LocalFileSystem,
    WritableFileSystem,
)
from prefect.logging import get_logger
from prefect.serializers import PickleSerializer, Serializer
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


@sync_compatible
async def get_default_result_storage() -> WritableFileSystem:
    """
    Generate a default file system for result storage.
    """
    default_block = PREFECT_DEFAULT_RESULT_STORAGE_BLOCK.value()

    if default_block is not None:
        return await resolve_result_storage(default_block)

    # otherwise, use the local file system
    basepath = PREFECT_LOCAL_STORAGE_PATH.value()
    return LocalFileSystem(basepath=str(basepath))


@sync_compatible
async def resolve_result_storage(
    result_storage: ResultStorage,
) -> WritableFileSystem:
    """
    Resolve one of the valid `ResultStorage` input types into a saved block
    document id and an instance of the block.
    """
    from prefect.client.orchestration import get_client

    client = get_client()
    if isinstance(result_storage, Block):
        storage_block = result_storage

        if storage_block._block_document_id is not None:
            # Avoid saving the block if it already has an identifier assigned
            storage_block_id = storage_block._block_document_id
        else:
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

    return storage_block


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


async def get_or_create_default_task_scheduling_storage() -> ResultStorage:
    """
    Generate a default file system for background task parameter/result storage.
    """
    default_block = PREFECT_TASK_SCHEDULING_DEFAULT_STORAGE_BLOCK.value()

    if default_block is not None:
        return await Block.load(default_block)

    # otherwise, use the local file system
    basepath = PREFECT_LOCAL_STORAGE_PATH.value()
    return LocalFileSystem(basepath=basepath)


def get_default_result_serializer() -> Serializer:
    """
    Generate a default file system for result storage.
    """
    return resolve_serializer(PREFECT_RESULTS_DEFAULT_SERIALIZER.value())


def get_default_persist_setting() -> bool:
    """
    Return the default option for result persistence (False).
    """
    return PREFECT_RESULTS_PERSIST_BY_DEFAULT.value()


def _format_user_supplied_storage_key(key: str) -> str:
    # Note here we are pinning to task runs since flow runs do not support storage keys
    # yet; we'll need to split logic in the future or have two separate functions
    runtime_vars = {key: getattr(prefect.runtime, key) for key in dir(prefect.runtime)}
    return key.format(**runtime_vars, parameters=prefect.runtime.task_run.parameters)


class ResultStore(BaseModel):
    """
    A utility to generate `Result` types.
    """

    result_storage: Optional[WritableFileSystem] = Field(default=None)
    persist_result: bool = Field(default_factory=get_default_persist_setting)
    cache_result_in_memory: bool = Field(default=True)
    serializer: Serializer = Field(default_factory=get_default_result_serializer)
    storage_key_fn: Callable[[], str] = Field(default=DEFAULT_STORAGE_KEY_FN)

    @property
    def result_storage_block_id(self) -> Optional[UUID]:
        if self.result_storage is None:
            return None
        return self.result_storage._block_document_id

    @sync_compatible
    async def update_for_flow(self, flow: "Flow") -> Self:
        """
        Create a new result store for a flow with updated settings.

        Args:
            flow: The flow to update the result store for.

        Returns:
            An updated result store.
        """
        update = {}
        if flow.result_storage is not None:
            update["result_storage"] = await resolve_result_storage(flow.result_storage)
        if flow.result_serializer is not None:
            update["serializer"] = resolve_serializer(flow.result_serializer)
        if flow.persist_result is not None:
            update["persist_result"] = flow.persist_result
        if flow.cache_result_in_memory is not None:
            update["cache_result_in_memory"] = flow.cache_result_in_memory
        if self.result_storage is None and update.get("result_storage") is None:
            update["result_storage"] = await get_default_result_storage()
        return self.model_copy(update=update)

    @sync_compatible
    async def update_for_task(self: Self, task: "Task") -> Self:
        """
        Create a new result store for a task.

        Args:
            task: The task to update the result store for.

        Returns:
            An updated result store.
        """
        update = {}
        if task.result_storage is not None:
            update["result_storage"] = await resolve_result_storage(task.result_storage)
        if task.result_serializer is not None:
            update["serializer"] = resolve_serializer(task.result_serializer)
        if task.persist_result is not None:
            update["persist_result"] = task.persist_result
        if task.cache_result_in_memory is not None:
            update["cache_result_in_memory"] = task.cache_result_in_memory
        if task.result_storage_key is not None:
            update["storage_key_fn"] = partial(
                _format_user_supplied_storage_key, task.result_storage_key
            )
        if self.result_storage is None and update.get("result_storage") is None:
            update["result_storage"] = await get_default_result_storage()
        return self.model_copy(update=update)

    @sync_compatible
    async def _read(self, key: str) -> "ResultRecord":
        """
        Read a result record from storage.

        This is the internal implementation. Use `read` or `aread` for synchronous and
        asynchronous result reading respectively.

        Args:
            key: The key to read the result record from.

        Returns:
            A result record.
        """
        if self.result_storage is None:
            self.result_storage = await get_default_result_storage()

        content = await self.result_storage.read_path(f"{key}")
        return ResultRecord.deserialize(content)

    def read(self, key: str) -> "ResultRecord":
        """
        Read a result record from storage.

        Args:
            key: The key to read the result record from.

        Returns:
            A result record.
        """
        return self._read(key=key, _sync=True)

    async def aread(self, key: str) -> "ResultRecord":
        """
        Read a result record from storage.

        Args:
            key: The key to read the result record from.

        Returns:
            A result record.
        """
        return await self._read(key=key, _sync=False)

    @sync_compatible
    async def _write(
        self,
        obj: Any,
        key: Optional[str] = None,
        expiration: Optional[DateTime] = None,
    ):
        """
        Write a result to storage.

        This is the internal implementation. Use `write` or `awrite` for synchronous and
        asynchronous result writing respectively.

        Args:
            key: The key to write the result record to.
            obj: The object to write to storage.
            expiration: The expiration time for the result record.
        """
        if self.result_storage is None:
            self.result_storage = await get_default_result_storage()
        key = key or self.storage_key_fn()

        record = ResultRecord(
            result=obj,
            metadata=ResultRecordMetadata(
                serializer=self.serializer, expiration=expiration, storage_key=key
            ),
        )
        await self.apersist_result_record(record)

    def write(self, key: str, obj: Any, expiration: Optional[DateTime] = None):
        """
        Write a result to storage.

        Handles the creation of a `ResultRecord` and its serialization to storage.

        Args:
            key: The key to write the result record to.
            obj: The object to write to storage.
            expiration: The expiration time for the result record.
        """
        return self._write(obj=obj, key=key, expiration=expiration, _sync=True)

    async def awrite(self, key: str, obj: Any, expiration: Optional[DateTime] = None):
        """
        Write a result to storage.

        Args:
            key: The key to write the result record to.
            obj: The object to write to storage.
            expiration: The expiration time for the result record.
        """
        return await self._write(obj=obj, key=key, expiration=expiration, _sync=False)

    @sync_compatible
    async def _persist_result_record(self, result_record: "ResultRecord"):
        """
        Persist a result record to storage.

        Args:
            result_record: The result record to persist.
        """
        if self.result_storage is None:
            self.result_storage = await get_default_result_storage()

        await self.result_storage.write_path(
            result_record.metadata.storage_key, content=result_record.serialize()
        )

    def persist_result_record(self, result_record: "ResultRecord"):
        """
        Persist a result record to storage.

        Args:
            result_record: The result record to persist.
        """
        return self._persist_result_record(result_record=result_record, _sync=True)

    async def apersist_result_record(self, result_record: "ResultRecord"):
        """
        Persist a result record to storage.

        Args:
            result_record: The result record to persist.
        """
        return await self._persist_result_record(
            result_record=result_record, _sync=False
        )

    @sync_compatible
    async def create_result(
        self,
        obj: R,
        key: Optional[str] = None,
        expiration: Optional[DateTime] = None,
    ) -> Union[R, "BaseResult[R]"]:
        """
        Create a `PersistedResult` for the given object.
        """
        # Null objects are "cached" in memory at no cost
        should_cache_object = self.cache_result_in_memory or obj is None

        if key:

            def key_fn():
                return key

            storage_key_fn = key_fn
        else:
            storage_key_fn = self.storage_key_fn

        if self.result_storage is None:
            self.result_storage = await get_default_result_storage()

        return await PersistedResult.create(
            obj,
            storage_block=self.result_storage,
            storage_block_id=self.result_storage_block_id,
            storage_key_fn=storage_key_fn,
            serializer=self.serializer,
            cache_object=should_cache_object,
            expiration=expiration,
            serialize_to_none=not self.persist_result,
        )

    # TODO: These two methods need to find a new home

    @sync_compatible
    async def store_parameters(self, identifier: UUID, parameters: Dict[str, Any]):
        record = ResultRecord(
            result=parameters,
            metadata=ResultRecordMetadata(
                serializer=self.serializer, storage_key=str(identifier)
            ),
        )
        await self.result_storage.write_path(
            f"parameters/{identifier}", content=record.serialize()
        )

    @sync_compatible
    async def read_parameters(self, identifier: UUID) -> Dict[str, Any]:
        record = ResultRecord.deserialize(
            await self.result_storage.read_path(f"parameters/{identifier}")
        )
        return record.result


def get_current_result_store() -> ResultStore:
    """
    Get the current result store.
    """
    from prefect.context import get_run_context

    try:
        run_context = get_run_context()
    except MissingContextError:
        result_store = ResultStore()
    else:
        result_store = run_context.result_store
    return result_store


class ResultRecordMetadata(BaseModel):
    """
    Metadata for a result record.
    """

    storage_key: Optional[str] = Field(
        default=None
    )  # optional for backwards compatibility
    expiration: Optional[DateTime] = Field(default=None)
    serializer: Serializer = Field(default_factory=PickleSerializer)
    prefect_version: str = Field(default=prefect.__version__)

    def dump_bytes(self) -> bytes:
        """
        Serialize the metadata to bytes.

        Returns:
            bytes: the serialized metadata
        """
        return self.model_dump_json(serialize_as_any=True).encode()

    @classmethod
    def load_bytes(cls, data: bytes) -> "ResultRecordMetadata":
        """
        Deserialize metadata from bytes.

        Args:
            data: the serialized metadata

        Returns:
            ResultRecordMetadata: the deserialized metadata
        """
        return cls.model_validate_json(data)


class ResultRecord(BaseModel, Generic[R]):
    """
    A record of a result.
    """

    metadata: ResultRecordMetadata
    result: R

    @property
    def expiration(self) -> Optional[DateTime]:
        return self.metadata.expiration

    @property
    def serializer(self) -> Serializer:
        return self.metadata.serializer

    def serialize_result(self) -> bytes:
        try:
            data = self.serializer.dumps(self.result)
        except Exception as exc:
            extra_info = (
                'You can try a different serializer (e.g. result_serializer="json") '
                "or disabling persistence (persist_result=False) for this flow or task."
            )
            # check if this is a known issue with cloudpickle and pydantic
            # and add extra information to help the user recover

            if (
                isinstance(exc, TypeError)
                and isinstance(self.result, BaseModel)
                and str(exc).startswith("cannot pickle")
            ):
                try:
                    from IPython import get_ipython

                    if get_ipython() is not None:
                        extra_info = inspect.cleandoc(
                            """
                            This is a known issue in Pydantic that prevents
                            locally-defined (non-imported) models from being
                            serialized by cloudpickle in IPython/Jupyter
                            environments. Please see
                            https://github.com/pydantic/pydantic/issues/8232 for
                            more information. To fix the issue, either: (1) move
                            your Pydantic class definition to an importable
                            location, (2) use the JSON serializer for your flow
                            or task (`result_serializer="json"`), or (3)
                            disable result persistence for your flow or task
                            (`persist_result=False`).
                            """
                        ).replace("\n", " ")
                except ImportError:
                    pass
            raise SerializationError(
                f"Failed to serialize object of type {type(self.result).__name__!r} with "
                f"serializer {self.serializer.type!r}. {extra_info}"
            ) from exc

        return data

    @model_validator(mode="before")
    @classmethod
    def coerce_old_format(cls, value: Any):
        if isinstance(value, dict):
            if "data" in value:
                value["result"] = value.pop("data")
            if "metadata" not in value:
                value["metadata"] = {}
            if "expiration" in value:
                value["metadata"]["expiration"] = value.pop("expiration")
            if "serializer" in value:
                value["metadata"]["serializer"] = value.pop("serializer")
            if "prefect_version" in value:
                value["metadata"]["prefect_version"] = value.pop("prefect_version")
        return value

    def serialize_metadata(self) -> bytes:
        return self.metadata.dump_bytes()

    def serialize(
        self,
    ) -> bytes:
        """
        Serialize the record to bytes.

        Returns:
            bytes: the serialized record

        """
        return (
            self.model_copy(update={"result": self.serialize_result()})
            .model_dump_json(serialize_as_any=True)
            .encode()
        )

    @classmethod
    def deserialize(cls, data: bytes) -> "ResultRecord[R]":
        """
        Deserialize a record from bytes.

        Args:
            data: the serialized record

        Returns:
            ResultRecord: the deserialized record
        """
        instance = cls.model_validate_json(data)
        if isinstance(instance.result, bytes):
            instance.result = instance.serializer.loads(instance.result)
        elif isinstance(instance.result, str):
            instance.result = instance.serializer.loads(instance.result.encode())
        return instance

    @classmethod
    def deserialize_from_result_and_metadata(
        cls, result: bytes, metadata: bytes
    ) -> "ResultRecord[R]":
        """
        Deserialize a record from separate result and metadata bytes.

        Args:
            result: the result
            metadata: the serialized metadata

        Returns:
            ResultRecord: the deserialized record
        """
        result_record_metadata = ResultRecordMetadata.load_bytes(metadata)
        return cls(
            metadata=result_record_metadata,
            result=result_record_metadata.serializer.loads(result),
        )


@register_base_type
class BaseResult(BaseModel, abc.ABC, Generic[R]):
    model_config = ConfigDict(extra="forbid")
    type: str

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


class PersistedResult(BaseResult):
    """
    Result type which stores a reference to a persisted result.

    When created, the user's object is serialized and stored. The format for the content
    is defined by `ResultRecord`. This reference contains metadata necessary for retrieval
    of the object, such as a reference to the storage block and the key where the
    content was written.
    """

    type: str = "reference"

    serializer_type: str
    storage_key: str
    storage_block_id: Optional[uuid.UUID] = None
    expiration: Optional[DateTime] = None
    serialize_to_none: bool = False

    _persisted: bool = PrivateAttr(default=False)
    _should_cache_object: bool = PrivateAttr(default=True)
    _storage_block: WritableFileSystem = PrivateAttr(default=None)
    _serializer: Serializer = PrivateAttr(default=None)

    @model_serializer(mode="wrap")
    def serialize_model(self, handler, info):
        if self.serialize_to_none:
            return None
        return handler(self, info)

    def _cache_object(
        self,
        obj: Any,
        storage_block: WritableFileSystem = None,
        serializer: Serializer = None,
    ) -> None:
        self._cache = obj
        self._storage_block = storage_block
        self._serializer = serializer

    @inject_client
    async def _get_storage_block(self, client: "PrefectClient") -> WritableFileSystem:
        if self._storage_block is not None:
            return self._storage_block
        elif self.storage_block_id is not None:
            block_document = await client.read_block_document(self.storage_block_id)
            self._storage_block = Block._from_block_document(block_document)
        else:
            self._storage_block = await get_default_result_storage()
        return self._storage_block

    @sync_compatible
    @inject_client
    async def get(
        self, ignore_cache: bool = False, client: "PrefectClient" = None
    ) -> R:
        """
        Retrieve the data and deserialize it into the original object.
        """
        if self.has_cached_object() and not ignore_cache:
            return self._cache

        result_store_kwargs = {}
        if self._serializer:
            result_store_kwargs["serializer"] = resolve_serializer(self._serializer)
        storage_block = await self._get_storage_block(client=client)
        result_store = ResultStore(result_storage=storage_block, **result_store_kwargs)

        record = await result_store.aread(self.storage_key)
        self.expiration = record.expiration

        if self._should_cache_object:
            self._cache_object(record.result)

        return record.result

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

        if self._persisted or self.serialize_to_none:
            # don't double write or overwrite
            return

        # load objects from a cache

        # first the object itself
        if obj is NotSet and not self.has_cached_object():
            raise ValueError("Cannot write a result that has no object cached.")
        obj = obj if obj is not NotSet else self._cache

        # next, the storage block
        storage_block = await self._get_storage_block(client=client)

        # finally, the serializer
        serializer = self._serializer
        if serializer is None:
            # this could error if the serializer requires kwargs
            serializer = Serializer(type=self.serializer_type)

        result_store = ResultStore(result_storage=storage_block, serializer=serializer)
        await result_store.awrite(
            obj=obj, key=self.storage_key, expiration=self.expiration
        )

        self._persisted = True

        if not self._should_cache_object:
            self._cache = NotSet

    @classmethod
    @sync_compatible
    async def create(
        cls: "Type[PersistedResult]",
        obj: R,
        storage_block: WritableFileSystem,
        storage_key_fn: Callable[[], str],
        serializer: Serializer,
        storage_block_id: Optional[uuid.UUID] = None,
        cache_object: bool = True,
        expiration: Optional[DateTime] = None,
        serialize_to_none: bool = False,
    ) -> "PersistedResult[R]":
        """
        Create a new result reference from a user's object.

        The object will be serialized and written to the storage block under a unique
        key. It will then be cached on the returned result.
        """
        key = storage_key_fn()
        if not isinstance(key, str):
            raise TypeError(
                f"Expected type 'str' for result storage key; got value {key!r}"
            )
        uri = cls._infer_path(storage_block, key)

        # in this case we store an absolute path
        if storage_block_id is None and uri is not None:
            key = str(uri)

        result = cls(
            serializer_type=serializer.type,
            storage_block_id=storage_block_id,
            storage_key=key,
            expiration=expiration,
            serialize_to_none=serialize_to_none,
        )

        object.__setattr__(result, "_should_cache_object", cache_object)
        # we must cache temporarily to allow for writing later
        # the cache will be removed on write
        result._cache_object(obj, storage_block=storage_block, serializer=serializer)

        return result

    def __eq__(self, other):
        if not isinstance(other, PersistedResult):
            return False
        return (
            self.type == other.type
            and self.serializer_type == other.serializer_type
            and self.storage_key == other.storage_key
            and self.storage_block_id == other.storage_block_id
            and self.expiration == other.expiration
        )
