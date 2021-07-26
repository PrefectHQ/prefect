"""
This module contains async and thread safe variables for passing runtime context data
"""
from contextvars import ContextVar
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from prefect.flows import FlowRunContext

flow_run: ContextVar["FlowRunContext"] = ContextVar("flow_run")
