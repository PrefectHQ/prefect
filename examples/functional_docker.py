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

## initialize tasks
container = CreateContainer(
    image_name="prefecthq/prefect",
    command='''python -c "from prefect import Flow; f = Flow('empty'); f.run()"''',
)
start = StartContainer()
logs = GetContainerLogs(trigger=always_run)
status_code = WaitOnContainer()


## set task dependencies via functional API

with Flow("Run a Prefect Flow in Docker") as flow:
    start_container = start(container_id=container)
    code = status_code(container_id=container, upstream_tasks=[start_container])
    collect_logs = logs(container_id=container, upstream_tasks=[code])

## run flow and print logs
flow_state = flow.run()

print("=" * 30)
print("Container Logs")
print("=" * 30)
print(flow_state.result[collect_logs].result)
