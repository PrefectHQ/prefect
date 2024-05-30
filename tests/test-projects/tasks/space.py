from prefect import task


@task
def spacewalk():
    return "Houston, I have a bad feeling about this mission."
