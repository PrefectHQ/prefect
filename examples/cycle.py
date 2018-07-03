from prefect import Flow, Task, task

@task
def a():
    return 1

@task
def b(x):
    return x + 1

@task
def c(x):
    return x + 1

@task
def d(x):
    return x + 1

with Flow("Cycle") as flow:
    head = a()
    node_1 = b(head)
    node_2 = c(node_1)
    node_3 = d(node_2)
    node_4 = node_1(node_3)
