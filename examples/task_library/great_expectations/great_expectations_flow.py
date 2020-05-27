from prefect import Flow, Parameter
from prefect.tasks.great_expectations import RunGreatExpectationsCheckpoint

ge_task = RunGreatExpectationsCheckpoint()

with Flow("great expectations example flow") as flow:
    checkpoint_name = Parameter("checkpoint_name")

    good_validation = ge_task(checkpoint_name)
    bad_validation = ge_task("guaranteed_failure_npi_checkpoint")

if __name__ == "__main__":
    flow.run(checkpoint_name="warning_npi_checkpoint")
