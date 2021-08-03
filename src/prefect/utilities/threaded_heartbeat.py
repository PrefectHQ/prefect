import threading
import time

import prefect
from prefect import config
from prefect.client import Client
from prefect.utilities.logging import get_logger


def heartbeat(id, num=None):
    logger = get_logger('heartbeat')
    client = Client()
    iter_count = 0
    with prefect.context({"flow_run_id": id, "running_with_backend": True}):

        try:  # Log signal-like exceptions that cannot be ignored

            while iter_count < (num or 1):

                try:  # Ignore (but log) client exceptions
                    client.update_flow_run_heartbeat(id)
                except Exception as exc:
                    logger.error(
                        f"Failed to send heartbeat with exception: {exc!r}",
                        exc_info=True,
                    )

                if num:
                    iter_count += 1
                time.sleep(config.cloud.heartbeat_interval)

        except BaseException as exc:
            logger.error(
                f"Heartbeat process encountered terminal exception: {exc!r}",
                exc_info=True,
            )
            raise


def thread_with_heartbeat(func, id, num=None):
    heartbeat_thread = threading.Thread(target=heartbeat, args={id: id, num: num}, daemon=True)
    heartbeat_thread.start()
    func()
