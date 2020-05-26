from prefect import Flow, Parameter
from prefect.tasks.great_expectations import GreatExpectationsTask

ge_task = GreatExpectationsTask(
    validation_operator_name="run_warning_and_failure_expectation_suites"
)

with Flow("great expectations example flow") as flow:
    datasource = Parameter("datasource")
    validation = ge_task(datasource=datasource)

if __name__ == "__main__":
    flow.run(datasource="npidata__dir")
