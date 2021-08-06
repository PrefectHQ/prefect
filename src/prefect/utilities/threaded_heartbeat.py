import threading
from contextlib import contextmanager

import prefect
from prefect import config
from prefect.client import Client
from prefect.utilities.logging import get_logger


class HeartbeatThread(threading.Thread):
    def __init__(self, stop_event, flow_run_id, num=None):
        threading.Thread.__init__(self)
        self.daemon = True  # 'daemonizes' the thread, so Python will terminate it when all non-daemonized threads have finished
        self.flow_run_id = flow_run_id
        self.num = num
        self.stop_event = stop_event

    def run(self):
        logger = get_logger('heartbeat')
        client = Client()
        iter_count = 0
        with prefect.context({"flow_run_id": self.flow_run_id, "running_with_backend": True}):
            with log_heartbeat_failure(logger):
                while iter_count < (self.num or 1) and (self.stop_event.is_set() is False):
                    send_heartbeat(self.flow_run_id, client, logger)
                    iter_count += 1 if self.num else 0
                    self.stop_event.wait(timeout=config.cloud.heartbeat_interval)


def send_heartbeat(flow_run_id, client, logger):
    try:  # Ignore (but log) client exceptions
        client.update_flow_run_heartbeat(flow_run_id)
    except Exception as exc:
        logger.error(
            f"Failed to send heartbeat with exception: {exc!r}",
            exc_info=True,
        )


@contextmanager
def log_heartbeat_failure(logger):
    try:
        yield
    except BaseException as exc:
        logger.error(
            f"Heartbeat process encountered terminal exception: {exc!r}",
            exc_info=True,
        )
        raise
