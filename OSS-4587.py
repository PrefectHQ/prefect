from prefect import flow, task


@task
def fetch_values() -> list[int]:
    result = [i for i in range(10)]
    return result


@task
def transform_value(value: int) -> int:
    if value == 6:
        raise ValueError
    result = value * 2
    return result


@task
def log_results(values: list[int]) -> None:
    for i in values:
        print(i)


@flow
def myflow():
    values = fetch_values()
    transformed = transform_value.map(values)

    # If this method is not called, the ValueError will be raised clearly and coherently
    # But if this method is called, the flow will fail here with an UnfinishedRun exception
    log_results(transformed)


if __name__ == "__main__":
    myflow()

# from random import randint
# from prefect import task, flow
# class DummyError(Exception):
#     pass

# @task
# def say_hello():
#     print("Hello, world!")

# @task
# def t1():
#     print("t1")

# @task
# def t2():
#     print("t2")

# @task
# def t3():
#     raise DummyError("t3")

# @task
# def mapper():
#     task_id = randint(1, 2)
#     task_instance = globals()[f"t{task_id}"] # dynamically select a task
#     return [
#         task_instance.submit(),
#         t3.submit()
#     ]

# @task
# def reducer(futures):
#     for future in futures:
#         try:
#             future.result()
#         except Exception as e:
#             print(f"Error: {e}")

# @flow
# def myflow():
#     say_hello()
#     futures = mapper()
#     reducer(futures)
#     say_hello()
#     return "OK"


# if __name__ == "__main__":
#     result = myflow()
