"""
This module contains async and thread safe variables for passing runtime context data
"""
from contextvars import ContextVar
from typing import Optional, TypeVar
from uuid import UUID

from pydantic import BaseModel

from prefect.client import OrionClient
from prefect.flows import Flow
from prefect.tasks import Task

T = TypeVar("T")


class ContextModel(BaseModel):
    """
    A base model for context data that forbids mutation and extra data while providing
    a context manager
    """

    # The context variable for storing data must be defined by the child class
    __var__: ContextVar

    class Config:
        allow_mutation = False
        arbitrary_types_allowed = True
        extra = "forbid"

    def __enter__(self):
        # We've frozen the rest of the data on the class but we'd like to still store
        # this token for resetting on context exit
        object.__setattr__(self, "__token", self.__var__.set(self))

    def __exit__(self, *_):
        self.__var__.reset(getattr(self, "__token"))

    @classmethod
    def get(cls: T) -> Optional[T]:
        return cls.__var__.get(None)


class FlowRunContext(ContextModel):
    flow: Flow
    flow_run_id: UUID
    # TODO: The Client cannot be pickled which means we cannot send this context over
    #       the network easily. The Client will need to implement __getstate__ and
    #       __setstate__ so it can be pickled w/ settings but create a new event loop
    #        on load
    client: OrionClient

    __var__ = ContextVar("flow_run")


class TaskRunContext(ContextModel):
    task: Task
    task_run_id: UUID

    __var__ = ContextVar("task_run")


class RunContext(ContextModel):
    task_run: Optional[TaskRunContext]
    flow_run: FlowRunContext

    def __enter__(self):
        raise TypeError("The `RunContext` cannot be set.")

    @classmethod
    def get(cls: T) -> Optional[T]:
        flow_run_ctx = FlowRunContext.get()
        if not flow_run_ctx:
            raise RuntimeError(
                "The run context could not be retrieved. "
                "You are not in a flow run context."
            )
        return cls(task_run=TaskRunContext.get(), flow_run=flow_run_ctx)
