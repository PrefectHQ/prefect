from prefect import flow


@flow(name="Hello Flow")
def hello_world(name="world"):
    print(f"Hello {name}!")


if __name__ == "__main__":
    hello_world("Marvin")
