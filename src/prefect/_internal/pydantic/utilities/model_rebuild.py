import typing

from typing_extensions import Self

from prefect._internal.pydantic._base_model import BaseModel
from prefect._internal.pydantic._flags import USE_V2_MODELS

T = typing.TypeVar("T", bound="BaseModel")


def model_rebuild(
    model_instance: typing.Type[T],
    *,
    force: bool = False,
    raise_errors: bool = True,
    _parent_namespace_depth: int = 2,
    _types_namespace: typing.Optional[typing.Dict[str, typing.Any]] = None,
) -> typing.Optional[bool]:
    """Try to rebuild the pydantic-core schema for the model.

    This may be necessary when one of the annotations is a ForwardRef which could not be resolved during
    the initial attempt to build the schema, and automatic rebuilding fails.

    Args:
        force: Whether to force the rebuilding of the model schema, defaults to `False`.
        raise_errors: Whether to raise errors, defaults to `True`.
        _parent_namespace_depth: The depth level of the parent namespace, defaults to 2.
        _types_namespace: The types namespace, defaults to `None`.

    Returns:
        Returns `None` if the schema is already "complete" and rebuilding was not required.
        If rebuilding _was_ required, returns `True` if rebuilding was successful, otherwise `False`.
    """

    if USE_V2_MODELS:
        return model_instance.model_rebuild(
            force=force,
            raise_errors=raise_errors,
            _parent_namespace_depth=_parent_namespace_depth,
            _types_namespace=_types_namespace,
        )
    else:
        return getattr(model_instance, "update_forward_refs")()


class ModelRebuildMixin(BaseModel):
    @classmethod
    def model_rebuild(
        cls: typing.Type["Self"],
        *,
        force: bool = False,
        raise_errors: bool = True,
        _parent_namespace_depth: int = 2,
        _types_namespace: typing.Optional[typing.Dict[str, typing.Any]] = None,
    ) -> typing.Optional[bool]:
        """Try to rebuild the pydantic-core schema for the model.

        This may be necessary when one of the annotations is a ForwardRef which could not be resolved during
        the initial attempt to build the schema, and automatic rebuilding fails.

        Args:
            force: Whether to force the rebuilding of the model schema, defaults to `False`.
            raise_errors: Whether to raise errors, defaults to `True`.
            _parent_namespace_depth: The depth level of the parent namespace, defaults to 2.
            _types_namespace: The types namespace, defaults to `None`.

        Returns:
            Returns `None` if the schema is already "complete" and rebuilding was not required.
            If rebuilding _was_ required, returns `True` if rebuilding was successful, otherwise `False`.
        """
        return model_rebuild(
            cls,
            force=force,
            raise_errors=raise_errors,
            _parent_namespace_depth=_parent_namespace_depth,
            _types_namespace=_types_namespace,
        )


__all__ = ["model_rebuild", "ModelRebuildMixin"]
