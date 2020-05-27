import prefect
from prefect import Task
from prefect.engine import signals
from prefect.utilities.tasks import defaults_from_attrs

try:
    import great_expectations as ge
except ImportError:
    pass


class RunGreatExpectationsCheckpoint(Task):
    def __init__(self, checkpoint_name: str = None,
    context_root_dir: str = None,
    runtime_environment: dict = {}, **kwargs):
        self.checkpoint_name = checkpoint_name
        self.context_root_dir = context_root_dir
        self.runtime_environment = runtime_environment

        super().__init__(**kwargs)

    @defaults_from_attrs("checkpoint_name", "context_root_dir", "runtime_environment")
    def run(self, checkpoint_name: str = None,
     context_root_dir: str = None,
    runtime_environment: dict = {},
    **kwargs):

        if checkpoint_name is None:
            raise ValueError('You must provide the checkpoint name.')
        
        context = ge.DataContext(context_root_dir=context_root_dir,
        runtime_environment=runtime_environment)
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
            run_id=prefect.context.get('task_id')
        )

        if not results['success']:
            raise signals.VALIDATIONFAIL