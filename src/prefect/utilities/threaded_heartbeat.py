import threading
import time
from contextlib import contextmanager

import prefect
from prefect import config
from prefect.client import Client
from prefect.utilities.logging import get_logger


class HeartbeatThread(threading.Thread):
    def __init__(self, stop_event, flow_run_id, num=None):
        threading.Thread.__init__(self)
        self.num = num
        self.daemon = True  # 'daemonizes' the thread, so Python will terminate it if all non-daemonized threads have finished running
        self.stop_event = stop_event

    def run(self):
        logger = get_logger('heartbeat')
        client = Client()
        iter_count = 0
        with prefect.context({"flow_run_id": id, "running_with_backend": True}):
            with log_heartbeat_failure(logger):
                while iter_count < (self.num or 1) or not self.stop_event.is_set():
                    send_heartbeat(self.id, client, logger)
                    iter_count += 1 if self.num else 0
                    time.sleep(config.cloud.heartbeat_interval)


def send_heartbeat(id, client, logger):
    try:  # Ignore (but log) client exceptions
        client.update_flow_run_heartbeat(id)
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


@contextmanager
def threaded_heartbeat(id, num=None):
    try:
        HEARTBEAT_STOP_EVENT = threading.Event()
        heartbeat = HeartbeatThread(HEARTBEAT_STOP_EVENT, id, num=None)
        heartbeat.start()
        yield
    finally:
        HEARTBEAT_STOP_EVENT.set()
