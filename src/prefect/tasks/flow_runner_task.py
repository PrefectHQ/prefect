# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

import prefect
from prefect.engine.executors import DEFAULT_EXECUTOR
from prefect.engine.state import State


class FlowRunnerTask(prefect.Task):
    def __init__(
        self, executor: prefect.engine.executors.Executor = None, **kwargs
    ) -> None:
        self.executor = executor
        super().__init__(**kwargs)

    def run(self, flow: prefect.Flow, parameters: dict = None) -> State:
        executor = (
            self.executor or prefect.context.get("_executor") or DEFAULT_EXECUTOR
        )
        runner = prefect.engine.FlowRunner(flow=flow)
        flow_state = runner.run(
            executor=executor,
            return_tasks=flow.reference_tasks(),
            parameters=parameters or dict(),
        )
        return flow_state
