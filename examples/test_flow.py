from prefect import flow, task

@task
def hello():
    print("hello world")

@flow
def test_flow():
    hello()

if __name__ == "__main__":
    test_flow()