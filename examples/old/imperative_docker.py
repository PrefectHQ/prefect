"""
This Prefect Flow creates a Container based on the latest prefect image, and
executes an empty Flow inside that container.  Make sure to pull `prefecthq/prefect` prior
to running this Flow.
"""

from prefect import Flow
from prefect.tasks.docker import (
    CreateContainer,
    GetContainerLogs,
    StartContainer,
    WaitOnContainer,
)
from prefect.triggers import always_run

container = CreateContainer(
    image_name="prefecthq/prefect",
    command='''python -c "from prefect import Flow; f = Flow('empty'); f.run()"''',
)
start = StartContainer()
logs = GetContainerLogs(trigger=always_run)
status_code = WaitOnContainer()


flow = Flow("Run a Prefect Flow in Docker")

## set individual task dependencies using imperative API
start.set_upstream(container, flow=flow, key="container_id")
logs.set_upstream(container, flow=flow, key="container_id")
status_code.set_upstream(container, flow=flow, key="container_id")

status_code.set_upstream(start, flow=flow)
logs.set_upstream(status_code, flow=flow)

## run flow and print logs
flow_state = flow.run()
print("=" * 30)
print("Container Logs")
print("=" * 30)
print(flow_state.result[logs].result)
