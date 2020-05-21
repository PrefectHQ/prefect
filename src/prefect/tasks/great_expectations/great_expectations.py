from prefect import Task
from prefect.utilities.tasks import defaults_from_attrs

try:
    import great_expectations as ge
    from great_expectations.validation_operators import (
        WarningAndFailureExpectationSuitesValidationOperator,
    )
except ImportError:
    pass


class GreatExpectationsTask(Task):
    def __init__(self, context: "ge.DataContext" = None, **kwargs):

        self.context = context or ge.DataContext()
        super().__init__(**kwargs)

    @defaults_from_attrs("context")
    def run(self, context: "ge.DataContext" = None, **kwargs):

        operator = WarningAndFailureExpectationSuitesValidationOperator(
            data_context,
            # action_list,
            # base_expectation_suite_name=None,
            # expectation_suite_name_suffixes=None,
            # stop_on_first_error=False,
            # slack_webhook=None,
            # notify_on="all",
        )

        results = context.run_validation_operator(
            assets_to_validate=inputs,
            run_id="some_string_that_uniquely_identifies_this_run",
            validation_operator_name="operator_instance_name",
            evaluation_parameters=None,
        )
