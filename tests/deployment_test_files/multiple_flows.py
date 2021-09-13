from prefect import flow


@flow
def hello_sun():
    print(f"Hello sun!")


@flow
def hello_moon():
    print(f"Hello moon!")
