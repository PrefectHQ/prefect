from prefect import Flow, Parameter
from prefect.tasks.great_expectations import RunGreatExpectationsValidation

ge_task = RunGreatExpectationsValidation()

with Flow("great expectations example flow") as flow:
    checkpoint_name = Parameter("checkpoint_name")
    validations = ge_task.map(checkpoint_name)

if __name__ == "__main__":
    flow.run(
        checkpoint_name=["warning_npi_checkpoint", "guaranteed_failure_npi_checkpoint"]
    )
