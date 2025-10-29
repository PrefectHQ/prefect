from __future__ import annotations

from typing import TYPE_CHECKING, Any, Union

from typing_extensions import TypeAlias

from prefect.flows import Flow
from prefect.logging import get_logger
from prefect.tasks import Task

if TYPE_CHECKING:
    import logging

logger: "logging.Logger" = get_logger("webserver")

FlowOrTask: TypeAlias = Union[Flow[Any, Any], Task[Any, Any]]
