import prefect


@prefect.task(log_stdout=True)
def say_hello(name):
    print(f"Hello {name}")


with prefect.Flow("hello-world") as hello_flow:
    name = prefect.Parameter("name", default="world")
    say_hello(name)
