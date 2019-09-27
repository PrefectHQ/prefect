import datetime

from prefect import Flow, Parameter, task
from prefect.engine.cache_validators import partial_parameters_only
from prefect.engine.result_handlers import JSONResultHandler, S3ResultHandler
from prefect.environments.execution import RemoteEnvironment
from prefect.environments.storage import Docker
from prefect.tasks.shell import ShellTask


@task(max_retries=5, retry_delay=datetime.timedelta(minutes=10))
def root_task():
    pass


@task(
    cache_for=datetime.timedelta(days=10),
    cache_validator=partial_parameters_only(["x"]),
    result_handler=JSONResultHandler(),
)
def cached_task(x, y):
    pass


x = Parameter("x")
y = Parameter("y", default=42)


@task(name="Big Name", checkpoint=True, result_handler=S3ResultHandler(bucket="blob"))
def terminal_task():
    pass


env = RemoteEnvironment(
    executor="prefect.engine.executors.DaskExecutor",
    executor_kwargs={"scheduler_address": "tcp://"},
)
storage = Docker(
    registry_url="prefecthq",
    image_name="flows",
    image_tag="welcome-flow",
    python_dependencies=["boto3"],
)

with Flow("test-serialization", storage=storage, environment=env) as f:
    result = cached_task.map(x, y, upstream_tasks=[root_task, root_task])
    terminal_task(upstream_tasks=[result, root_task])


f.storage.add_flow(f)
