from prefect import flow, get_run_logger, task

default_str = "I am the default message"


@task
def log_message(msg: str):
    logger = get_run_logger()
    logger.info(f"Your 'msg' parameter was {msg}")


@task
def log_num(num: int):
    logger = get_run_logger()
    logger.info(f"Your 'num' parameter was {num}")


@flow(name="parameters")
def param_flow(purpose, msg: str = default_str, num: int = 42):
    logger = get_run_logger()
    logger.info(purpose)

    log_message()
    log_num()


if __name__ == "__main__":
    param_flow()
