import typing

from prefect._internal.pydantic._flags import USE_V2_MODELS

if typing.TYPE_CHECKING:
    from prefect._internal.pydantic._base_model import BaseModel

T = typing.TypeVar("T", bound="BaseModel")

if USE_V2_MODELS:

    def model_rebuild(  # type: ignore[no-redef]
        model_instance: typing.Type[T],
        *,
        force: bool = False,
        raise_errors: bool = True,
        _parent_namespace_depth: int = 2,
        _types_namespace: typing.Optional[typing.Dict[str, typing.Any]] = None,
    ) -> typing.Optional[bool]:
        return model_instance.model_rebuild(
            force=force,
            raise_errors=raise_errors,
            _parent_namespace_depth=_parent_namespace_depth,
            _types_namespace=_types_namespace,
        )

else:

    def model_rebuild(  # type: ignore[no-redef]
        model_instance: typing.Type[T],
        *,
        force: bool = False,
        raise_errors: bool = True,
        _parent_namespace_depth: int = 2,
        _types_namespace: typing.Optional[typing.Dict[str, typing.Any]] = None,
    ) -> typing.Optional[bool]:
        return getattr(model_instance, "update_forward_refs")()


__all__ = ["model_rebuild"]
