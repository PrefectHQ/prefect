from prefect import Flow, Task, task
from prefect.environments import Container, Secret

username = Secret("username")
username.value = "josh"
password = Secret("password")
password.value = "12345"

container = Container(image="python3:alpine", name="basic_container",
                        secrets=[username, password])

@task
def extract():
    return 5

with Flow("ETL", environment=container) as flow:
    e = extract()

flow.run()
