# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

from typing import Any

import prefect
from prefect.engine.state import State


class FlowRunnerTask(prefect.Task):
    def __init__(
        self,
        flow_runner_class: prefect.engine.flow_runner.FlowRunner = None,
        executor: prefect.engine.executors.Executor = None,
        **kwargs: Any
    ):
        self.flow_runner_class = flow_runner_class
        self.executor = executor
        super().__init__(**kwargs)

    def run(self, flow: prefect.Flow, parameters: dict = None) -> State:  # type: ignore
        runner_cls = (
            self.flow_runner_class or prefect.engine.get_default_flow_runner_class()
        )
        flow_state = runner_cls(flow=flow).run(
            executor=self.executor or prefect.context.get("executor"),
            return_tasks=flow.reference_tasks(),
            parameters=parameters or dict(),
        )
        return flow_state
