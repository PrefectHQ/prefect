"""
Great Expectations checkpoints are combinations of data source, expectation suite, and
validation operators configuration that can be used to run Great Expectations actions.
Checkpoints are the preferred deployment of validation configuration; you can read more about
setting up checkpoints [at the Great Expectation
docs](https://docs.greatexpectations.io/en/latest/tutorials/getting_started/set_up_your_first_checkpoint.html#set-up-your-first-checkpoint).

You can use these task library tasks to interact with your Great Expectations checkpoint from a
Prefect flow.
"""
import prefect
from prefect import Task
from prefect.engine import signals
from prefect.utilities.tasks import defaults_from_attrs


import great_expectations as ge

from typing import Optional


class RunGreatExpectationsCheckpoint(Task):
    """
    Task for running a Great Expectations checkpoint. For this task to run properly, it must be
    run above your great_expectations directory or configured with the `context_root_dir` for
    your great_expectations directory on the local file system of the worker process.

    Args:
        - checkpoint_name (str): the name of the checkpoint; should match the filename of the
            checkpoint without .py
        - context_root_dir (str): the absolute or relative path to the directory holding your
            `great_expectations.yml`
        - runtime_environment (dict): a dictionary of great expectation config key-value pairs
            to overwrite your config in `great_expectations.yml`
        - run_name (str): the name of this Great Expectation validation run; defaults to the
            task slug
        - **kwargs (dict, optional): additional keyword arguments to pass to the Task constructor
    """

    def __init__(
        self,
        checkpoint_name: str = None,
        context_root_dir: str = None,
        runtime_environment: Optional[dict] = None,
        run_name: str = None,
        **kwargs
    ):
        self.checkpoint_name = checkpoint_name
        self.context_root_dir = context_root_dir
        self.runtime_environment = runtime_environment or dict()
        self.run_name = run_name

        super().__init__(**kwargs)

    @defaults_from_attrs(
        "checkpoint_name", "context_root_dir", "runtime_environment", "run_name"
    )
    def run(
        self,
        checkpoint_name: str = None,
        context_root_dir: str = None,
        runtime_environment: Optional[dict] = None,
        run_name: str = None,
        **kwargs
    ):
        """
        Task run method.

        Args:
            - checkpoint_name (str): the name of the checkpoint; should match the filename of
                the checkpoint without .py
            - context_root_dir (str): the absolute or relative path to the directory holding
                your `great_expectations.yml`
            - runtime_environment (dict): a dictionary of great expectation config key-value
                pairs to overwrite your config in `great_expectations.yml`
            - run_name (str): the name of this  Great Expectation validation run; defaults to
                the task slug
            - **kwargs (dict, optional): additional keyword arguments to pass to the Task
                constructor

        Raises:
            - 'signals.VALIDATIONFAIL' if the validation was not a success
        Returns:
            - result
                ('great_expectations.validation_operators.types.validation_operator_result.ValidationOperatorResult'):
                The Great Expectations metadata returned from the validation

        """

        if checkpoint_name is None:
            raise ValueError("You must provide the checkpoint name.")

        runtime_environment = runtime_environment or dict()

        context = ge.DataContext(
            context_root_dir=context_root_dir, runtime_environment=runtime_environment
        )
        checkpoint = context.get_checkpoint(checkpoint_name)

        batches_to_validate = []
        for batch in checkpoint["batches"]:
            batch_kwargs = batch["batch_kwargs"]
            for suite_name in batch["expectation_suite_names"]:
                suite = context.get_expectation_suite(suite_name)
                batch = context.get_batch(batch_kwargs, suite)
                batches_to_validate.append(batch)

        results = context.run_validation_operator(
            checkpoint["validation_operator_name"],
            assets_to_validate=batches_to_validate,
            run_id={"run_name": prefect.context.get("task_slug")},
        )

        if results.success is False:
            raise signals.VALIDATIONFAIL(result=results)

        return results
