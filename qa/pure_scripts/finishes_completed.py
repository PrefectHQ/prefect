from prefect import flow, get_run_logger, task

purpose = """
The purpose of this flow is to finish in a completed state.

Expected behavior: `parent_task` will pass results to `first_child`
and `second_child`. `first_child` will pass results to `grand_child`. 
The flow should finish in a completed state.
"""


@task
def parent_task():
    return 256


@task
def first_child(from_parent):
    return 512


@task
def second_child(from_parent):
    return 42


@task
def grand_child(from_child):
    return 1024


@flow
def finishes_completed():
    logger = get_run_logger()
    logger.info(purpose)

    parent_res = parent_task()
    c1_res = first_child(parent_res)
    c2_res = second_child(parent_res)
    grand_child(c1_res)


if __name__ == "__main__":
    finishes_completed()
