from prefect.server.task_queue import _task_queue_module_path
from prefect.settings import PREFECT_MESSAGING_BROKER, temporary_settings


def test_redis_messaging_uses_durable_task_queue() -> None:
    with temporary_settings({PREFECT_MESSAGING_BROKER: "prefect_redis.messaging"}):
        assert _task_queue_module_path() == "prefect_redis.task_queue"


def test_other_messaging_uses_process_local_task_queue() -> None:
    with temporary_settings(
        {PREFECT_MESSAGING_BROKER: "prefect.server.utilities.messaging.memory"}
    ):
        assert _task_queue_module_path() == "prefect.server.task_queue.memory"
