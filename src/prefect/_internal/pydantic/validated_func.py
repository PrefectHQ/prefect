"""
Pure Pydantic v2 implementation of function argument validation.

This module provides validation of function arguments without calling the function,
compatible with Python 3.14+ (no Pydantic v1 dependency).
"""

from __future__ import annotations

import inspect
from typing import Any, Callable, ClassVar, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    create_model,
    field_validator,
)

# Special field names for validation
# These match pydantic.v1.decorator constants for compatibility
V_ARGS_NAME = "v__args"
V_KWARGS_NAME = "v__kwargs"
V_POSITIONAL_ONLY_NAME = "v__positional_only"
V_DUPLICATE_KWARGS = "v__duplicate_kwargs"


class ValidatedFunction:
    """
    Validates function arguments using Pydantic v2 without calling the function.

    This class inspects a function's signature and creates a Pydantic model
    that can validate arguments passed to the function, including handling
    of *args, **kwargs, positional-only parameters, and duplicate arguments.

    Example:
        ```python
        def greet(name: str, age: int = 0):
            return f"Hello {name}, you are {age} years old"

        vf = ValidatedFunction(greet)

        # Validate arguments
        values = vf.validate_call_args(("Alice",), {"age": 30})
        # Returns: {"name": "Alice", "age": 30}

        # Invalid arguments will raise ValidationError
        vf.validate_call_args(("Bob",), {"age": "not a number"})
        # Raises: ValidationError
        ```
    """

    def __init__(
        self,
        function: Callable[..., Any],
        config: ConfigDict | None = None,
    ):
        """
        Initialize the validated function.

        Args:
            function: The function to validate arguments for
            config: Optional Pydantic ConfigDict or dict configuration

        Raises:
            ValueError: If function parameters conflict with internal field names
        """
        self.raw_function = function
        self.signature = inspect.signature(function)
        self.arg_mapping: dict[int, str] = {}
        self.positional_only_args: set[str] = set()
        self.v_args_name = V_ARGS_NAME
        self.v_kwargs_name = V_KWARGS_NAME
        self._needs_rebuild = False

        # Check for conflicts with internal field names
        reserved_names = {
            V_ARGS_NAME,
            V_KWARGS_NAME,
            V_POSITIONAL_ONLY_NAME,
            V_DUPLICATE_KWARGS,
        }
        param_names = set(self.signature.parameters.keys())
        conflicts = reserved_names & param_names
        if conflicts:
            raise ValueError(
                f"Function parameters conflict with internal field names: {conflicts}. "
                f"These names are reserved: {reserved_names}"
            )

        # Build the validation model
        fields, takes_args, takes_kwargs, has_forward_refs = self._build_fields()
        self._create_model(fields, takes_args, takes_kwargs, config, has_forward_refs)

    def _build_fields(self) -> tuple[dict[str, Any], bool, bool, bool]:
        """
        Build field definitions from function signature.

        Returns:
            Tuple of (fields_dict, takes_args, takes_kwargs, has_forward_refs)
        """
        fields: dict[str, Any] = {}
        takes_args = False
        takes_kwargs = False
        has_forward_refs = False
        position = 0

        for param_name, param in self.signature.parameters.items():
            if param.kind == inspect.Parameter.VAR_POSITIONAL:
                takes_args = True
                continue

            if param.kind == inspect.Parameter.VAR_KEYWORD:
                takes_kwargs = True
                continue

            # Track positional-only parameters
            if param.kind == inspect.Parameter.POSITIONAL_ONLY:
                self.positional_only_args.add(param_name)

            # Map position to parameter name
            if param.kind in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            ):
                self.arg_mapping[position] = param_name
                position += 1

            # Determine type and default
            annotation = (
                param.annotation if param.annotation != inspect.Parameter.empty else Any
            )

            # Check if annotation is a string (forward reference)
            if isinstance(annotation, str):
                has_forward_refs = True

            if param.default == inspect.Parameter.empty:
                # Required parameter
                fields[param_name] = (annotation, Field(...))
            else:
                # Optional parameter with default
                fields[param_name] = (annotation, Field(default=param.default))

        # Always add args/kwargs fields for validation, even if function doesn't accept them
        fields[self.v_args_name] = (Optional[list[Any]], Field(default=None))
        fields[self.v_kwargs_name] = (Optional[dict[str, Any]], Field(default=None))

        # Add special validation fields
        fields[V_POSITIONAL_ONLY_NAME] = (Optional[list[str]], Field(default=None))
        fields[V_DUPLICATE_KWARGS] = (Optional[list[str]], Field(default=None))

        return fields, takes_args, takes_kwargs, has_forward_refs

    def _create_model(
        self,
        fields: dict[str, Any],
        takes_args: bool,
        takes_kwargs: bool,
        config: ConfigDict | None,
        has_forward_refs: bool,
    ) -> None:
        """Create the Pydantic validation model."""
        pos_args = len(self.arg_mapping)

        # Process config
        # Note: ConfigDict is a TypedDict, so we can't use isinstance() in Python 3.14
        # Instead, check if it's a dict-like object and merge with defaults
        if config is None:
            config_dict = ConfigDict(extra="forbid")
        else:
            config_dict = config.copy()
            if "extra" not in config_dict:
                config_dict["extra"] = "forbid"

        # Create base model with validators
        class DecoratorBaseModel(BaseModel):
            model_config: ClassVar[ConfigDict] = config_dict

            @field_validator(V_ARGS_NAME, check_fields=False)
            @classmethod
            def check_args(cls, v: Optional[list[Any]]) -> Optional[list[Any]]:
                if takes_args or v is None:
                    return v

                raise TypeError(
                    f"{pos_args} positional argument{'s' if pos_args != 1 else ''} "
                    f"expected but {pos_args + len(v)} given"
                )

            @field_validator(V_KWARGS_NAME, check_fields=False)
            @classmethod
            def check_kwargs(
                cls, v: Optional[dict[str, Any]]
            ) -> Optional[dict[str, Any]]:
                if takes_kwargs or v is None:
                    return v

                plural = "" if len(v) == 1 else "s"
                keys = ", ".join(map(repr, v.keys()))
                raise TypeError(f"unexpected keyword argument{plural}: {keys}")

            @field_validator(V_POSITIONAL_ONLY_NAME, check_fields=False)
            @classmethod
            def check_positional_only(cls, v: Optional[list[str]]) -> None:
                if v is None:
                    return

                plural = "" if len(v) == 1 else "s"
                keys = ", ".join(map(repr, v))
                raise TypeError(
                    f"positional-only argument{plural} passed as keyword "
                    f"argument{plural}: {keys}"
                )

            @field_validator(V_DUPLICATE_KWARGS, check_fields=False)
            @classmethod
            def check_duplicate_kwargs(cls, v: Optional[list[str]]) -> None:
                if v is None:
                    return

                plural = "" if len(v) == 1 else "s"
                keys = ", ".join(map(repr, v))
                raise TypeError(f"multiple values for argument{plural}: {keys}")

        # Create the model dynamically
        model_name = f"{self.raw_function.__name__.title()}Model"
        self.model = create_model(
            model_name,
            __base__=DecoratorBaseModel,
            **fields,
        )

        # Rebuild the model with the original function's namespace to resolve forward references
        # This is necessary when using `from __future__ import annotations` or when
        # parameters reference types not in the current scope
        # Only rebuild if we detected forward references to avoid performance overhead
        # If rebuild fails (e.g., forward-referenced types not yet defined), defer to validation time
        if has_forward_refs:
            try:
                self.model.model_rebuild(_types_namespace=self.raw_function.__globals__)
            except (NameError, AttributeError):
                # Forward references can't be resolved yet (e.g., types defined after decorator)
                # Model will be rebuilt during validate_call_args when types are available
                self._needs_rebuild = True

    def validate_call_args(
        self, args: tuple[Any, ...], kwargs: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Validate function arguments and return normalized parameters.

        Args:
            args: Positional arguments
            kwargs: Keyword arguments

        Returns:
            Dictionary mapping parameter names to values

        Raises:
            ValidationError: If arguments don't match the function signature
        """
        # Build the values dict for validation
        values: dict[str, Any] = {}
        var_args: list[Any] = []
        var_kwargs: dict[str, Any] = {}
        positional_only_passed_as_kw: list[str] = []
        duplicate_kwargs: list[str] = []

        # Process positional arguments
        for i, arg in enumerate(args):
            if i in self.arg_mapping:
                param_name = self.arg_mapping[i]
                if param_name in kwargs:
                    # Duplicate: both positional and keyword
                    duplicate_kwargs.append(param_name)
                values[param_name] = arg
            else:
                # Extra positional args go into *args
                var_args.append(arg)

        # Process keyword arguments
        for key, value in kwargs.items():
            if key in values:
                # Already set by positional arg
                continue

            # Check if this is a positional-only param passed as keyword
            if key in self.positional_only_args:
                positional_only_passed_as_kw.append(key)
                continue

            # Check if this is a known parameter
            if key in self.signature.parameters:
                values[key] = value
            else:
                # Unknown parameter goes into **kwargs
                var_kwargs[key] = value

        # Add special fields
        if var_args:
            values[self.v_args_name] = var_args
        if var_kwargs:
            values[self.v_kwargs_name] = var_kwargs
        if positional_only_passed_as_kw:
            values[V_POSITIONAL_ONLY_NAME] = positional_only_passed_as_kw
        if duplicate_kwargs:
            values[V_DUPLICATE_KWARGS] = duplicate_kwargs

        # Rebuild model if needed to resolve any forward references that weren't available
        # at initialization time (e.g., when using `from __future__ import annotations`)
        # Only rebuild if we previously failed to resolve forward refs at init time
        if self._needs_rebuild:
            # Try rebuilding with raise_errors=False to handle any remaining issues gracefully
            self.model.model_rebuild(
                _types_namespace=self.raw_function.__globals__, raise_errors=False
            )
            # Clear the flag - we only need to rebuild once
            self._needs_rebuild = False

        # Validate using the model
        try:
            validated = self.model.model_validate(values)
        except ValidationError as e:
            # Convert ValidationError to TypeError for certain cases to match Python's behavior
            # Check if the error is about extra kwargs
            for error in e.errors():
                if error.get("type") == "extra_forbidden" and error.get("loc") == (
                    "kwargs",
                ):
                    # This is an extra keyword argument error
                    extra_keys = error.get("input", {})
                    if isinstance(extra_keys, dict):
                        plural = "" if len(extra_keys) == 1 else "s"
                        keys = ", ".join(map(repr, extra_keys.keys()))
                        raise TypeError(f"unexpected keyword argument{plural}: {keys}")
            # For other validation errors, re-raise as-is
            raise

        # Extract only the actual function parameters
        result: dict[str, Any] = {}
        for param_name in self.signature.parameters.keys():
            param = self.signature.parameters[param_name]

            if param.kind == inspect.Parameter.VAR_POSITIONAL:
                result[param_name] = getattr(validated, self.v_args_name) or []
            elif param.kind == inspect.Parameter.VAR_KEYWORD:
                result[param_name] = getattr(validated, self.v_kwargs_name) or {}
            else:
                # Regular parameter
                value = getattr(validated, param_name)
                result[param_name] = value

        return result

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """
        Validate arguments and call the function.

        Args:
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            The result of calling the function with validated arguments
        """
        validated_params = self.validate_call_args(args, kwargs)
        return self.raw_function(**validated_params)
