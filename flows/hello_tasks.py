from prefect import flow, get_run_logger, task


@task
def say_hello(name: str):
    get_run_logger().info(f"Hello {name}!")


@flow
def hello(name: str = "world", count: int = 1):
    say_hello.map(f"{name}-{i}" for i in range(count))


if __name__ == "__main__":
    hello(count=3)
