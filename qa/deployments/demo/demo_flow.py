from prefect import flow, get_run_logger, task


@task
def first_task():
    return 42


@task
def second_task(msg, result):
    logger = get_run_logger()
    logger.info(
        f"Hello from second task!\nYour message is '{msg}'.\nThe first result was {result}"
    )


@flow(name="demo")
def pipeline(purpose, msg):
    logger = get_run_logger()  # All flows should begin by getting a run logger
    logger.info(purpose)  # and then logging the purpose of the flow.
    result_1 = first_task()
    second_task(msg, result_1)


if __name__ == "__main__":
    pipeline()
