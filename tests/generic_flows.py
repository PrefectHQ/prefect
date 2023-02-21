from prefect import flow


@flow(name=f"{__name__}.identity")
def identity(x):
    return x
