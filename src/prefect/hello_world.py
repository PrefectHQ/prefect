"""
A very basic 'hello-world' flow for getting started quickly
Examples:
    Run this flow locally
    --------------------
    >>> from prefect.hello_world import hello_flow
    >>> hello_flow.run()
    Run this flow with a different parameter than the default
    --------------------------------------------------------
    >>> from prefect.hello_world import hello_flow
    >>> hello_flow.run(name="marvin")
    Register this flow with the Prefect backend
    ------------------------------------------
    $ prefect create project 'default'
    $ prefect register --project default -m prefect.hello_world
    Run this flow with the Prefect backend and agent
    ------------------------------------------
    $ prefect run --name "hello-world" --watch
"""

from prefect import task, Flow, Parameter


@task(log_stdout=True)
def say_hello(to: str) -> None:
    print(f"Hello {to}")


@task()
def capitalize(word: str) -> str:
    return word.capitalize()


with Flow("hello-world") as hello_flow:
    name = Parameter("name", default="world")
    say_hello(capitalize(name))
