from prefect import Flow, task

# ------------------------------------
# define some tasks


@task
def numbers_task():
    return [1, 2, 3]


@task
def map_task(x):
    return x + 1


@task
def reduce_task(x):
    return sum(x)


# ------------------------------------
# build a flow

with Flow("Map / Reduce 🤓") as flow:
    numbers = numbers_task()
    first_map = map_task.map(numbers)
    second_map = map_task.map(first_map)
    reduction = reduce_task(second_map)


# ------------------------------------
# run the flow

state = flow.run()
assert state.result[reduction].result == 12
