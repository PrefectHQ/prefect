from __future__ import annotations

import inspect
import uuid
from typing import (
    TYPE_CHECKING,
    Any,
    Generic,
    Optional,
    TypeVar,
    Union,
    cast,
)
from uuid import UUID

from pydantic import (
    BaseModel,
    Field,
    ValidationError,
    model_validator,
)

import prefect
from prefect.exceptions import (
    SerializationError,
)
from prefect.serializers import PickleSerializer, Serializer
from prefect.types import DateTime

if TYPE_CHECKING:
    pass


ResultSerializer = Union[Serializer, str]
LITERAL_TYPES: set[type] = {type(None), bool, UUID}
R = TypeVar("R")


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
    storage_block_id: Optional[uuid.UUID] = Field(default=None)

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

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, ResultRecordMetadata):
            return False
        return (
            self.storage_key == other.storage_key
            and self.expiration == other.expiration
            and self.serializer == other.serializer
            and self.prefect_version == other.prefect_version
            and self.storage_block_id == other.storage_block_id
        )


class ResultRecord(BaseModel, Generic[R]):
    """
    A record of a result.
    """

    metadata: ResultRecordMetadata
    result: R

    @property
    def expiration(self) -> DateTime | None:
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
                    from IPython.core.getipython import get_ipython

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
    def coerce_old_format(cls, value: dict[str, Any] | Any) -> dict[str, Any]:
        if isinstance(value, dict):
            if TYPE_CHECKING:  # TODO: # isintance doesn't accept generic parameters
                value = cast(dict[str, Any], value)
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
    def deserialize(
        cls, data: bytes, backup_serializer: Serializer | None = None
    ) -> "ResultRecord[R]":
        """
        Deserialize a record from bytes.

        Args:
            data: the serialized record
            backup_serializer: The serializer to use to deserialize the result record. Only
                necessary if the provided data does not specify a serializer.

        Returns:
            ResultRecord: the deserialized record
        """
        try:
            instance = cls.model_validate_json(data)
        except ValidationError:
            if backup_serializer is None:
                raise
            else:
                result = backup_serializer.loads(data)
                return cls(
                    metadata=ResultRecordMetadata(serializer=backup_serializer),
                    result=result,
                )
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

    def __eq__(self, other: Any | "ResultRecord[Any]") -> bool:
        if not isinstance(other, ResultRecord):
            return False
        return self.model_dump(include={"metadata", "result"}) == other.model_dump(
            include={"metadata", "result"}
        )
