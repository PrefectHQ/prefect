from pprint import pprint

from prefect import flow, task
from prefect.dag import build_dag


@task
def called():
    assert False, "No tasks should execute"


@task
def submitted():
    assert False, "No tasks should execute"


@task
def conditional():
    assert False, "No tasks should execute"


@task
def for_item_in_result(x):
    assert False, "No tasks should execute"


@task
def for_item_in_range(x):
    assert False, "No tasks should execute"


@task
def if_false():
    assert False, "No tasks should execute"


@task
def if_true():
    assert False, "No tasks should execute"


@task
def receives_future(x):
    assert False, "No tasks should execute"


@flow
def my_flow():
    called()

    result = conditional()
    if result:
        if_true()
    else:
        if_false()

    for i in range(10):
        for_item_in_range(i)

    for item in result:
        for_item_in_result(item)

    future = submitted.submit()
    receives_future(future)


dag = build_dag(my_flow)
pprint(dag)
