from time import sleep

from prefect import flow, task


@task(name="hello")
def task_hello_world():
    print("hello world")


@flow(name="test flow")
def test_flow():
    task_hello_world()
    sleep(500)
