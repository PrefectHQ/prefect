from prefect import Flow, task


@task
def extract():
    return [1, 2, 3]


@task
def transform(x):
    return [i * 10 for i in x]


@task
def load(y):
    print("Received y: {}".format(y))


with Flow("ETL") as flow:
    e = extract()
    t = transform(e)
    l = load(t)

flow.run()
