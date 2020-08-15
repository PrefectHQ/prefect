import uuid
import six
import time

from prefect import Task
from prefect.client import Secret
from prefect.utilities.tasks import defaults_from_attrs
from prefect.utilities.exceptions import PrefectError

from prefect.contrib.tasks.databricks.databricks_hook import DatabricksHook


def _deep_string_coerce(content, json_path='json'):
    """
    Coerces content or all values of content if it is a dict to a string. The
    function will throw if content contains non-string or non-numeric types.

    The reason why we have this function is because the ``self.json`` field must be a
    dict with only string values. This is because ``render_template`` will fail
    for numerical values.
    """
    c = _deep_string_coerce
    if isinstance(content, six.string_types):
        return content
    elif isinstance(content, six.integer_types + (float,)):
        # Databricks can tolerate either numeric or string types in the API backend.
        return str(content)
    elif isinstance(content, (list, tuple)):
        return [c(e, '{0}[{1}]'.format(json_path, i)) for i, e in enumerate(content)]
    elif isinstance(content, dict):
        return {k: c(v, '{0}[{1}]'.format(json_path, k))
                for k, v in list(content.items())}
    else:
        param_type = type(content)
        msg = 'Type {0} used for parameter {1} is not a number or a string' \
            .format(param_type, json_path)
        raise ValueError(msg)


def _handle_databricks_task_execution(task, hook, log):
    """
    Handles the Databricks + Prefect lifecycle logic for a Databricks task

    Args:
        - task (prefect.Task) : Prefect task being handled
        - hook (prefect.contrib.tasks.databricks.databricks_hook.DatabricksHook): Databricks Hook
        - log (logger): Prefect logging instance
    """

    log.info('Run submitted with run_id: %s', task.run_id)
    run_page_url = hook.get_run_page_url(task.run_id)

    log.info('Run submitted with config : %s', task.json)

    log.info('View run status, Spark UI, and logs at %s', run_page_url)
    while True:
        run_state = hook.get_run_state(task.run_id)
        if run_state.is_terminal:
            if run_state.is_successful:
                log.info('%s completed successfully.', task.name)
                log.info('View run status, Spark UI, and logs at %s', run_page_url)
                return
            else:
                error_message = '{t} failed with terminal state: {s}'.format(
                    t=task.name,
                    s=run_state)
                raise PrefectError(error_message)
        else:
            log.info('%s in run state: %s', task.name, run_state)
            log.info('View run status, Spark UI, and logs at %s', run_page_url)
            log.info('Sleeping for %s seconds.', task.polling_period_seconds)
            time.sleep(task.polling_period_seconds)

class DatabricksSubmitRun(Task):
    """
    Submits a Spark job run to Databricks using the
    `api/2.0/jobs/runs/submit
    <https://docs.databricks.com/api/latest/jobs.html#runs-submit>`_
    API endpoint.

    There are two ways to instantiate this task.

    In the first way, you can take the JSON payload that you typically use
    to call the ``api/2.0/jobs/runs/submit`` endpoint and pass it directly
    to our ``DatabricksSubmitRun`` task through the ``json`` parameter.
    For example ::

        json = {
          'new_cluster': {
            'spark_version': '2.1.0-db3-scala2.11',
            'num_workers': 2
          },
          'notebook_task': {
            'notebook_path': '/Users/prefect@example.com/PrepareData',
          },
        }
        notebook_run = DatabricksSubmitRun(task_id='notebook_run', json=json)

    Another way to accomplish the same thing is to use the named parameters
    of the ``DatabricksSubmitRun`` directly. Note that there is exactly
    one named parameter for each top level parameter in the ``runs/submit``
    endpoint. In this method, your code would look like this: ::

        new_cluster = {
          'spark_version': '2.1.0-db3-scala2.11',
          'num_workers': 2
        }
        notebook_task = {
          'notebook_path': '/Users/prefect@example.com/PrepareData',
        }
        notebook_run = DatabricksSubmitRun(
            task_id='notebook_run',
            new_cluster=new_cluster,
            notebook_task=notebook_task)

    In the case where both the json parameter **AND** the named parameters
    are provided, they will be merged together. If there are conflicts during the merge,
    the named parameters will take precedence and override the top level ``json`` keys.

    Currently the named parameters that ``DatabricksSubmitRun`` task supports are
        - ``spark_jar_task``
        - ``notebook_task``
        - ``new_cluster``
        - ``existing_cluster_id``
        - ``libraries``
        - ``run_name``
        - ``timeout_seconds``

    Args:
        - databricks_conn_id (str, optional): The name of the Prefect Secret to use.
            By default and in the common case this will be ``DATABRICKS_CONNECTION_STRING``.
            Structure must be a string of valid JSON. To use token based authentication, provide 
            the key ``token`` in the string for the connection and create the key ``host``.

                PREFECT__CONTEXT__SECRETS__DATABRICKS_CONNECTION_STRING='{"host": "abcdef.xyz", "login": "ghijklmn", "password": "opqrst"}'

                OR

                PREFECT__CONTEXT__SECRETS__DATABRICKS_CONNECTION_STRING='{"host": "abcdef.xyz", "token": "ghijklmn"}'

        - json (dict, optional): A JSON object containing API parameters which will be passed
            directly to the ``api/2.0/jobs/runs/submit`` endpoint. The other named parameters
            (i.e. ``spark_jar_task``, ``notebook_task``..) to this task will
            be merged with this json dictionary if they are provided.
            If there are conflicts during the merge, the named parameters will
            take precedence and override the top level json keys. (templated)

            .. seealso::
                For more information about templating see :ref:`jinja-templating`.
                https://docs.databricks.com/api/latest/jobs.html#runs-submit
    
        - spark_jar_task (dict, optional): The main class and parameters for the JAR task. Note that
            the actual JAR is specified in the ``libraries``.
            *EITHER* ``spark_jar_task`` *OR* ``notebook_task`` should be specified.
            This field will be templated.

            .. seealso::
                https://docs.databricks.com/api/latest/jobs.html#jobssparkjartask

        - notebook_task (dict, optional): The notebook path and parameters for the notebook task.
            *EITHER* ``spark_jar_task`` *OR* ``notebook_task`` should be specified.
            This field will be templated.

            .. seealso::
                https://docs.databricks.com/api/latest/jobs.html#jobsnotebooktask

        - new_cluster (dict, optional): Specs for a new cluster on which this task will be run.
            *EITHER* ``new_cluster`` *OR* ``existing_cluster_id`` should be specified.
            This field will be templated.

            .. seealso::
                https://docs.databricks.com/api/latest/jobs.html#jobsclusterspecnewcluster

        - existing_cluster_id (str, optional): ID for existing cluster on which to run this task.
            *EITHER* ``new_cluster`` *OR* ``existing_cluster_id`` should be specified.
            This field will be templated.

        - libraries (list of dicts, optional): Libraries which this run will use.
            This field will be templated.

            .. seealso::
                https://docs.databricks.com/api/latest/libraries.html#managedlibrarieslibrary

        - run_name (str, optional): The run name used for this task.
            By default this will be set to the Prefect ``task_id``. This ``task_id`` is a
            required parameter of the superclass ``Task``.
            This field will be templated.

        - timeout_seconds (int, optional): The timeout for this run. By default a value of 0 is used
            which means to have no timeout.
            This field will be templated.

        - polling_period_seconds (int, optional): Controls the rate which we poll for the result of
            this run. By default the task will poll every 30 seconds.

        - databricks_retry_limit (int, optional): Amount of times retry if the Databricks backend is
            unreachable. Its value must be greater than or equal to 1.
    
        - databricks_retry_delay (float, optional): Number of seconds to wait between retries (it
            might be a floating point number).

        - **kwargs (dict, optional): additional keyword arguments to pass to the
            Task constructor
    """

    def __init__(
        self,
        databricks_conn_secret: str = "DATABRICKS_CONNECTION_STRING",
        json=None,
        spark_jar_task=None,
        notebook_task=None,
        new_cluster=None,
        existing_cluster_id=None,
        libraries=None,
        run_name=None,
        timeout_seconds=None,
        polling_period_seconds=30,
        databricks_retry_limit=3,
        databricks_retry_delay=1,
        **kwargs
    ) -> None:

        self.databricks_conn_id = Secret(databricks_conn_secret).get()
        
        self.json = json or {}
        self.polling_period_seconds = polling_period_seconds
        self.databricks_retry_limit = databricks_retry_limit
        self.databricks_retry_delay = databricks_retry_delay

        if spark_jar_task is not None:
            self.json['spark_jar_task'] = spark_jar_task
        if notebook_task is not None:
            self.json['notebook_task'] = notebook_task
        if new_cluster is not None:
            self.json['new_cluster'] = new_cluster
        if existing_cluster_id is not None:
            self.json['existing_cluster_id'] = existing_cluster_id
        if libraries is not None:
            self.json['libraries'] = libraries
        if run_name is not None:
            self.json['run_name'] = run_name
        if timeout_seconds is not None:
            self.json['timeout_seconds'] = timeout_seconds
        if 'run_name' not in self.json:
            self.json['run_name'] = run_name or "Run Submitted by Prefect"

        # Validate the dictionary to a valid JSON object
        self.json = _deep_string_coerce(self.json)

        # This variable will be used in case our task gets killed.
        self.run_id = None

        super().__init__(**kwargs)

    def get_hook(self):
        return DatabricksHook(
            self.databricks_conn_id,
            retry_limit=self.databricks_retry_limit,
            retry_delay=self.databricks_retry_delay
        )

    def run(
        self,
    ) -> str:
        """
        Task run method.

        Args:
            - json (dict, optional): A JSON object containing API parameters which will be passed
                directly to the ``api/2.0/jobs/runs/submit`` endpoint. The other named parameters
                (i.e. ``spark_jar_task``, ``notebook_task``..) to this task will
                be merged with this json dictionary if they are provided.
                If there are conflicts during the merge, the named parameters will
                take precedence and override the top level json keys. (templated)

                .. seealso::
                    For more information about templating see :ref:`jinja-templating`.
                    https://docs.databricks.com/api/latest/jobs.html#runs-submit
        
            - spark_jar_task (dict, optional): The main class and parameters for the JAR task. Note that
                the actual JAR is specified in the ``libraries``.
                *EITHER* ``spark_jar_task`` *OR* ``notebook_task`` should be specified.
                This field will be templated.

                .. seealso::
                    https://docs.databricks.com/api/latest/jobs.html#jobssparkjartask

            - notebook_task (dict, optional): The notebook path and parameters for the notebook task.
                *EITHER* ``spark_jar_task`` *OR* ``notebook_task`` should be specified.
                This field will be templated.

                .. seealso::
                    https://docs.databricks.com/api/latest/jobs.html#jobsnotebooktask

            - new_cluster (dict, optional): Specs for a new cluster on which this task will be run.
                *EITHER* ``new_cluster`` *OR* ``existing_cluster_id`` should be specified.
                This field will be templated.

                .. seealso::
                    https://docs.databricks.com/api/latest/jobs.html#jobsclusterspecnewcluster

            - existing_cluster_id (str, optional): ID for existing cluster on which to run this task.
                *EITHER* ``new_cluster`` *OR* ``existing_cluster_id`` should be specified.
                This field will be templated.

            - libraries (list of dicts, optional): Libraries which this run will use.
                This field will be templated.

                .. seealso::
                    https://docs.databricks.com/api/latest/libraries.html#managedlibrarieslibrary

            - run_name (str, optional): The run name used for this task.
                By default this will be set to the Prefect ``task_id``. This ``task_id`` is a
                required parameter of the superclass ``Task``.
                This field will be templated.

            - timeout_seconds (int, optional): The timeout for this run. By default a value of 0 is used
                which means to have no timeout.
                This field will be templated.

            - polling_period_seconds (int, optional): Controls the rate which we poll for the result of
                this run. By default the task will poll every 30 seconds.

            - databricks_retry_limit (int, optional): Amount of times retry if the Databricks backend is
                unreachable. Its value must be greater than or equal to 1.
        
            - databricks_retry_delay (float, optional): Number of seconds to wait between retries (it
                might be a floating point number).
           

        Returns:
            - str: Run id of the submitted run.
        """

        # Initialize Databricks Connections
        hook = self.get_hook()

        # Submit the job
        self.run_id = hook.submit_run(self.json)
        _handle_databricks_task_execution(self, hook, self.logger)

        return self.run_id
