from prefect import flow


@flow
def howdy(name: str) -> str:
    return f"howdy, {name}!"
