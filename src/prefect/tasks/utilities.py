import inspect
from typing import Any

from pydantic_core.core_schema import ValidationInfo


def generate_task_name(v: Any, info: ValidationInfo) -> str:
    return v if v else info.data["fn"].__name__


def generate_task_description(v: Any, info: ValidationInfo) -> Any:
    return v if v else inspect.getdoc(info.data["fn"])


def evaluate_retry_delay_seconds(v: Any, info: ValidationInfo) -> Any:
    return v if not callable(v) else v(info.data["retries"])


def check_reserved_arguments() -> None:
    return None


def get_default_retries() -> int:
    from prefect.settings import PREFECT_TASK_DEFAULT_RETRIES

    return PREFECT_TASK_DEFAULT_RETRIES.value()


def get_default_retry_delay() -> int:
    from prefect.settings import (
        PREFECT_TASK_DEFAULT_RETRY_DELAY_SECONDS,  # type: ignore
    )

    return PREFECT_TASK_DEFAULT_RETRY_DELAY_SECONDS.value()  # type: ignore
