import prefect


@prefect.flow
def howdy() -> str:
    return "howdy!"
