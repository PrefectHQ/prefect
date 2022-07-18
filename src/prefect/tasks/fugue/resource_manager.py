from typing import Any
from prefect.tasks.core.resource_manager import resource_manager
from fugue import make_execution_engine, ExecutionEngine


@resource_manager
class FugueExecutionEngine:
    def __init__(self, engine: Any, conf: Any):
        self._raw_engine, self._conf = engine, conf

    def setup(self) -> ExecutionEngine:
        return make_execution_engine(self._raw_engine, self._conf)

    def cleanup(self, engine: ExecutionEngine) -> None:
        engine.stop()
