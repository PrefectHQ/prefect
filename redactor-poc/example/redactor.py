import logging.config
from logging import Formatter
from pathlib import Path

import prefect
import yaml
from prefect import task, Flow
from prefect.utilities.local_file_redactor import LocalFileRedactor
from prefect.utilities.logging_debug import dump_logging_cfg


def configure_redactor_logging():
    standard_formatter = Formatter(prefect.config.logging.format)
    redacted_formatter = LocalFileRedactor.Formatter(
        root_dir="/tmp", format="%(asctime)s - %(name)s - %(levelname)s - Redacted"
    )
    redacted_handler = LocalFileRedactor.Handler(root_dir="/tmp")
    redacted_handler.setFormatter(standard_formatter)
    # Set the task logger to write to a file.
    task_logger = prefect.context.get("logger")
    task_logger.addHandler(redacted_handler)

    task_runner_logger = logging.getLogger("prefect.CloudTaskRunner")
    task_runner_logger.addHandler(redacted_handler)

    prefect_logger = logging.getLogger("prefect")
    for handler in prefect_logger.handlers:
        if isinstance(handler, prefect.utilities.logging.CloudHandler):
            handler.setFormatter(redacted_formatter)


@task
def redacted_log():
    configure_redactor_logging()
    logger = prefect.context.get("logger")
    with Path("/tmp/logging.cfg").open("wt") as fh:
        dump_logging_cfg(fh)
    logger.info("SSN: 123-45-6789")
    # with Path("/tmp/logging-trace.txt").open("at") as fh:
    #     fh.write(f"Logger name: {logger.name}\n")


@task
def redacted_exception():
    configure_redactor_logging()
    with Path("/tmp/logging.cfg").open("wt") as fh:
        dump_logging_cfg(fh)
    1 / 0


def build_flow():
    with Flow("Redacted") as flow:
        redacted_log()
        redacted_exception()
    return flow


if __name__ == "__main__":
    flow = build_flow()
    # flow.run()
    flow.register(project_name="local-only")
