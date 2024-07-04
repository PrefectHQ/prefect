from contextvars import ContextVar, Token
from typing import (
    Any,
    Dict,
    Optional,
    Type,
)

from pydantic import BaseModel, ConfigDict, PrivateAttr
from typing_extensions import Self


class ContextModel(BaseModel):
    """
    A base model for context data that forbids mutation and extra data while providing
    a context manager
    """

    # The context variable for storing data must be defined by the child class
    __var__: ContextVar
    _token: Optional[Token] = PrivateAttr(None)
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra="forbid",
    )

    def __enter__(self):
        if self._token is not None:
            raise RuntimeError(
                "Context already entered. Context enter calls cannot be nested."
            )
        self._token = self.__var__.set(self)
        return self

    def __exit__(self, *_):
        if not self._token:
            raise RuntimeError(
                "Asymmetric use of context. Context exit called without an enter."
            )
        self.__var__.reset(self._token)
        self._token = None

    @classmethod
    def get(cls: Type[Self]) -> Optional[Self]:
        """Get the current context instance"""
        return cls.__var__.get(None)

    def model_copy(
        self: Self, *, update: Optional[Dict[str, Any]] = None, deep: bool = False
    ):
        """
        Duplicate the context model, optionally choosing which fields to include, exclude, or change.

        Attributes:
            include: Fields to include in new model.
            exclude: Fields to exclude from new model, as with values this takes precedence over include.
            update: Values to change/add in the new model. Note: the data is not validated before creating
                the new model - you should trust this data.
            deep: Set to `True` to make a deep copy of the model.

        Returns:
            A new model instance.
        """
        new = super().model_copy(update=update, deep=deep)
        # Remove the token on copy to avoid re-entrance errors
        new._token = None
        return new

    def serialize(self) -> Dict[str, Any]:
        """
        Serialize the context model to a dictionary that can be pickled with cloudpickle.
        """
        return self.model_dump(exclude_unset=True)
