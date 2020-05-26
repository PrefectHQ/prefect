import prefect
from prefect import Task
from prefect.engine import signals
from prefect.utilities.tasks import defaults_from_attrs

try:
    import great_expectations as ge
except ImportError:
    pass


class GreatExpectationsTask(Task):
    def __init__(self, validation_operator_name: str = None, datasource: str = None, **kwargs):

        self.validation_operator_name = validation_operator_name
        self.datasource = datasource
        super().__init__(**kwargs)

    @defaults_from_attrs("validation_operator_name", "datasource")
    def run(self, validation_operator_name: str = None, datasource: str = None, **kwargs):

        if validation_operator_name is None:
            raise ValueError("You must provide an operator name that matches one in your great expectations configuration file.")
        if datasource is None:
            raise ValueError("You must provide a datasource name that matches one in your great expectations configuration.")

        context = ge.DataContext()

        #####
        # datasource = context.get_datasource(datasource)
        # batch_kwargs_generator_name = datasource.list_batch_kwargs_generators()[0]['name']
        # batch_kwargs_generator = datasource.get_batch_kwargs_generator(name=batch_kwargs_generator_name)
        # data_asset_name = datasource.get_available_data_asset_names()[batch_kwargs_generator_name]['names'][0][0]
        # batch_kwargs = datasource.build_batch_kwargs(batch_kwargs_generator_name, data_asset_name=data_asset_name)
        # batch = datasource.get_batch(batch_kwargs=batch_kwargs)

    
        batch_kwargs = {'path': 'data/npidata/npidata_pfile_20190902-20190908.csv', 'datasource': datasource}
        expectation_suite_name = 'npidata_pfile_20190902-20190908.warning'
        tup = (batch_kwargs, expectation_suite_name)

        results = context.run_validation_operator(
            validation_operator_name,
            assets_to_validate=[tup],
            run_id=prefect.context.get('task_id'),
            base_expectation_suite_name='npidata_pfile_20190902-20190908'
        )

        if not results['success']:
            raise signals.VALIDATIONFAIL