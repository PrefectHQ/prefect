from prefect import flow, get_run_logger

purpose = """
The purpose of this flow is make sure that the UI can handle
a large number of logs.

Expected behavior: this flow should produce 1000 logs, which
alternate between info, warning, and error based on their n%3.
"""


@flow
def lots_of_logs():
    logger = get_run_logger()
    logger.info(purpose)

    for i in range(1000):
        if i % 3 == 0:
            logger.info(f"{i} is divisible by 3")
        elif i % 3 == 1:
            logger.warning(f"{i}/3 has a remainder of 1")
        else:
            logger.error(f"{i}/3 has a remainder of 2")


if __name__ == "__main__":
    lots_of_logs()
