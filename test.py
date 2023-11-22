from prefect import flow


@flow(retries=5)
def my_flow():
    raise ValueError("This is a test")


if __name__ == "__main__":
    my_flow.serve(name="my-first-deployment")
