from prefect import task


@task
def do_the_dishes():
    return "The dishes are :sparkles: clean!"
