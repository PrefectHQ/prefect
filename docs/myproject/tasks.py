from prefect import task


@task
def my_background_task(name: str):
    ...
