from prefect import flow, task


@task
def smoke_test_task(*args, **kwargs):
    print(args, kwargs)


@flow
def smoke_test_flow():
    smoke_test_task("foo", "bar", baz="qux")


smoke_test_flow()
