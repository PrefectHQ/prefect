import prefect


@prefect.task(log_stdout=True)
def say_hello(name: str) -> None:
    print(f"Hello {name}")


with prefect.Flow("hello-world") as flow:
    name = prefect.Parameter("name", default="world")
    say_hello(name)
