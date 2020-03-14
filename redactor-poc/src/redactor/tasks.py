import logging

task_logger = logging.getLogger("Task")
task_runner_logger = logging.getLogger("TaskRunner")


def task_plain_message():
    task_logger.info("Simple message")


def task_uncaught_exception():
    1 / 0


def task_runner(task):
    try:
        task()
    except Exception as exc:
        task_runner_logger.exception("Uncaught exception")
