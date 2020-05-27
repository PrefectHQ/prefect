from prefect import Flow, Parameter
from prefect.tasks.great_expectations import RunGreatExpectationsCheckpoint

ge_task = RunGreatExpectationsCheckpoint()

with Flow("great expectations example flow") as flow:
    checkpoint_name = Parameter("checkpoint_name")

    validation = ge_task(checkpoint_name)

if __name__ == "__main__":
    flow.run(checkpoint_name="my_checkpoint")
