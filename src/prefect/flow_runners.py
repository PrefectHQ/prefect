from pydantic import BaseModel

from typing import Dict
from prefect.orion.schemas.core import FlowRunnerSettings


_FLOW_RUNNERS: Dict[str, "FlowRunner"] = {}


class FlowRunner(BaseModel):
    env: Dict[str, str]

    def to_settings(self):
        return FlowRunnerSettings(typename=type(self).__name__, config=self.dict())

    @classmethod
    def from_settings(cls, settings: FlowRunnerSettings):
        return cls(**settings.dict())


def register_flow_runner(cls):
    _FLOW_RUNNERS[cls.__name__] = cls
    return cls


def lookup_flow_runner(typename: str) -> FlowRunner:
    """Return the serializer implementation for the given ``encoding``"""
    try:
        return _FLOW_RUNNERS[typename]
    except KeyError:
        raise ValueError(f"Unregistered flow runner {typename!r}")


@register_flow_runner
class SubprocessFlowRunner(FlowRunner):
    pass
