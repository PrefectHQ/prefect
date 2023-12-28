import os
import signal

from prefect import flow
from prefect.logging.loggers import flow_run_logger


def on_crashed(flow, flow_run, state):
    logger = flow_run_logger(flow_run, flow)
    logger.info("This flow crashed!")


@flow(on_crashed=[on_crashed], log_prints=True)
def crashing_flow():
    print("Oh boy, here I go crashing again...")
    os.kill(os.getpid(), signal.SIGTERM)
