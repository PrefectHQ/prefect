import six
import time
from typing import List, Dict

from prefect import Task
from prefect.utilities.tasks import defaults_from_attrs
from prefect.utilities.exceptions import PrefectError

from prefect.tasks.databricks.databricks_hook import DatabricksHook


def _deep_string_coerce(content, json_path="json"):
    """
    Coerces content or all values of content if it is a dict to a string. The
    function will throw if content contains non-string or non-numeric types.

    The reason why we have this function is because the `self.json` field must be a
    dict with only string values. This is because `render_template` will fail
    for numerical values.
    """
    c = _deep_string_coerce
    if isinstance(content, six.string_types):
        return content
    elif isinstance(content, six.integer_types + (float,)):
        # Databricks can tolerate either numeric or string types in the API backend.
        return str(content)
    elif isinstance(content, (list, tuple)):
        return [c(e, "{0}[{1}]".format(json_path, i)) for i, e in enumerate(content)]
    elif isinstance(content, dict):
        return {
            k: c(v, "{0}[{1}]".format(json_path, k)) for k, v in list(content.items())
        }
    else:
        param_type = type(content)
        msg = "Type {0} used for parameter {1} is not a number or a string".format(
            param_type, json_path
        )
        raise ValueError(msg)


def _handle_databricks_task_execution(task, hook, log):
    """
    Handles the Databricks + Prefect lifecycle logic for a Databricks task

    Args:
        - task (prefect.Task) : Prefect task being handled
        - hook (prefect.contrib.tasks.databricks.databricks_hook.DatabricksHook): Databricks Hook
        - log (logger): Prefect logging instance
    """

    log.info("Run submitted with run_id: %s", task.run_id)
    run_page_url = hook.get_run_page_url(task.run_id)

    log.info("Run submitted with config : %s", task.json)

    log.info("View run status, Spark UI, and logs at %s", run_page_url)
    while True:
        run_state = hook.get_run_state(task.run_id)
        if run_state.is_terminal:
            if run_state.is_successful:
                log.info("%s completed successfully.", task.name)
                log.info("View run status, Spark UI, and logs at %s", run_page_url)
                return
            else:
                error_message = "{t} failed with terminal state: {s}".format(
                    t=task.name, s=run_state
                )
                raise PrefectError(error_message)
        else:
            log.info("%s in run state: %s", task.name, run_state)
            log.info("View run status, Spark UI, and logs at %s", run_page_url)
            log.info("Sleeping for %s seconds.", task.polling_period_seconds)
            time.sleep(task.polling_period_seconds)


class DatabricksSubmitRun(Task):
    """
    Submits a Spark job run to Databricks using the
    `api/2.0/jobs/runs/submit
    <https://docs.databricks.com/api/latest/jobs.html#runs-submit>`_
    API endpoint.

    There are two ways to instantiate this task.

    In the first way, you can take the JSON payload that you typically use
    to call the `api/2.0/jobs/runs/submit` endpoint and pass it directly
    to our `DatabricksSubmitRun` task through the `json` parameter.
    For example:

    ```
    json = {
        'new_cluster': {
        'spark_version': '2.1.0-db3-scala2.11',
        'num_workers': 2
        },
        'notebook_task': {
        'notebook_path': '/Users/prefect@example.com/PrepareData',
        },
    }

    conn = PrefectSecret('DATABRICKS_CONNECTION_STRING')
    notebook_run = DatabricksSubmitRun(databricks_conn_string=conn, json=json)
    ```

    Another way to accomplish the same thing is to use the named parameters
    of the `DatabricksSubmitRun` directly. Note that there is exactly
    one named parameter for each top level parameter in the `runs/submit`
    endpoint. In this method, your code would look like this:

    ```
    new_cluster = {
        'spark_version': '2.1.0-db3-scala2.11',
        'num_workers': 2
    }
    notebook_task = {
        'notebook_path': '/Users/prefect@example.com/PrepareData',
    }

    conn = PrefectSecret('DATABRICKS_CONNECTION_STRING')
    notebook_run = DatabricksSubmitRun(
        databricks_conn_string=conn,
        new_cluster=new_cluster,
        notebook_task=notebook_task)
    ```

    In the case where both the json parameter **AND** the named parameters
    are provided, they will be merged together. If there are conflicts during the merge,
    the named parameters will take precedence and override the top level `json` keys.

    This task requires a Databricks connection to be specified as a Prefect secret and can
    be passed to the task like so:

    ```
    from prefect.tasks.secrets import PrefectSecret
    from prefect.contrib.tasks.databricks import DatabricksSubmitRun

    with Flow('my flow') as flow:
        conn = PrefectSecret('DATABRICKS_CONNECTION_STRING')
        DatabricksSubmitRun(databricks_conn_string=conn, json=...)
    ```

    Currently the named parameters that `DatabricksSubmitRun` task supports are

    - `spark_jar_task`
    - `notebook_task`
    - `new_cluster`
    - `existing_cluster_id`
    - `libraries`
    - `run_name`
    - `timeout_seconds`

    Args:
        - databricks_conn_secret (dict, optional): Dictionary representation of the Databricks Connection
            String. Structure must be a string of valid JSON. To use token based authentication, provide
            the key `token` in the string for the connection and create the key `host`.
            `PREFECT__CONTEXT__SECRETS__DATABRICKS_CONNECTION_STRING=
            '{"host": "abcdef.xyz", "login": "ghijklmn", "password": "opqrst"}'`
            OR
            `PREFECT__CONTEXT__SECRETS__DATABRICKS_CONNECTION_STRING=
            '{"host": "abcdef.xyz", "token": "ghijklmn"}'`
            See documentation of the `DatabricksSubmitRun` Task to see how to pass in the connection
            string using `PrefectSecret`.
        - json (dict, optional): A JSON object containing API parameters which will be passed
            directly to the `api/2.0/jobs/runs/submit` endpoint. The other named parameters
            (i.e. `spark_jar_task`, `notebook_task`..) to this task will
            be merged with this json dictionary if they are provided.
            If there are conflicts during the merge, the named parameters will
            take precedence and override the top level json keys. (templated)
            For more information about templating see :ref:`jinja-templating`.
            https://docs.databricks.com/api/latest/jobs.html#runs-submit
        - spark_jar_task (dict, optional): The main class and parameters for the JAR task. Note that
            the actual JAR is specified in the `libraries`.
            *EITHER* `spark_jar_task` *OR* `notebook_task` should be specified.
            This field will be templated.
            https://docs.databricks.com/api/latest/jobs.html#jobssparkjartask
        - notebook_task (dict, optional): The notebook path and parameters for the notebook task.
            *EITHER* `spark_jar_task` *OR* `notebook_task` should be specified.
            This field will be templated.
            https://docs.databricks.com/api/latest/jobs.html#jobsnotebooktask
        - new_cluster (dict, optional): Specs for a new cluster on which this task will be run.
            *EITHER* `new_cluster` *OR* `existing_cluster_id` should be specified.
            This field will be templated.
            https://docs.databricks.com/api/latest/jobs.html#jobsclusterspecnewcluster
        - existing_cluster_id (str, optional): ID for existing cluster on which to run this task.
            *EITHER* `new_cluster` *OR* `existing_cluster_id` should be specified.
            This field will be templated.
        - libraries (list of dicts, optional): Libraries which this run will use.
            This field will be templated.
            https://docs.databricks.com/api/latest/libraries.html#managedlibrarieslibrary
        - run_name (str, optional): The run name used for this task.
            By default this will be set to the Prefect `task_id`. This `task_id` is a
            required parameter of the superclass `Task`.
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
        databricks_conn_secret: dict = None,
        json: dict = None,
        spark_jar_task: dict = None,
        notebook_task: dict = None,
        new_cluster: dict = None,
        existing_cluster_id: str = None,
        libraries: List[Dict] = None,
        run_name: str = None,
        timeout_seconds: int = None,
        polling_period_seconds: int = 30,
        databricks_retry_limit: int = 3,
        databricks_retry_delay: float = 1,
        **kwargs
    ) -> None:

        self.databricks_conn_secret = databricks_conn_secret
        self.json = json or {}
        self.spark_jar_task = spark_jar_task
        self.notebook_task = notebook_task
        self.new_cluster = new_cluster
        self.existing_cluster_id = existing_cluster_id
        self.libraries = libraries
        self.run_name = run_name
        self.timeout_seconds = timeout_seconds
        self.polling_period_seconds = polling_period_seconds
        self.databricks_retry_limit = databricks_retry_limit
        self.databricks_retry_delay = databricks_retry_delay

        self.run_id = None

        super().__init__(**kwargs)

    def get_hook(self):
        return DatabricksHook(
            self.databricks_conn_secret,
            retry_limit=self.databricks_retry_limit,
            retry_delay=self.databricks_retry_delay,
        )

    @defaults_from_attrs(
        "databricks_conn_secret",
        "json",
        "spark_jar_task",
        "notebook_task",
        "new_cluster",
        "existing_cluster_id",
        "libraries",
        "run_name",
        "timeout_seconds",
        "polling_period_seconds",
        "databricks_retry_limit",
        "databricks_retry_delay",
    )
    def run(
        self,
        databricks_conn_secret: dict = None,
        json: dict = None,
        spark_jar_task: dict = None,
        notebook_task: dict = None,
        new_cluster: dict = None,
        existing_cluster_id: str = None,
        libraries: List[Dict] = None,
        run_name: str = None,
        timeout_seconds: int = None,
        polling_period_seconds: int = 30,
        databricks_retry_limit: int = 3,
        databricks_retry_delay: float = 1,
    ) -> str:
        """
        Task run method.

        Args:

        - databricks_conn_secret (dict, optional): Dictionary representation of the Databricks Connection
            String. Structure must be a string of valid JSON. To use token based authentication, provide
            the key `token` in the string for the connection and create the key `host`.
            `PREFECT__CONTEXT__SECRETS__DATABRICKS_CONNECTION_STRING=
            '{"host": "abcdef.xyz", "login": "ghijklmn", "password": "opqrst"}'`
            OR
            `PREFECT__CONTEXT__SECRETS__DATABRICKS_CONNECTION_STRING=
            '{"host": "abcdef.xyz", "token": "ghijklmn"}'`
            See documentation of the `DatabricksSubmitRun` Task to see how to pass in the connection
            string using `PrefectSecret`.
        - json (dict, optional): A JSON object containing API parameters which will be passed
            directly to the `api/2.0/jobs/runs/submit` endpoint. The other named parameters
            (i.e. `spark_jar_task`, `notebook_task`..) to this task will
            be merged with this json dictionary if they are provided.
            If there are conflicts during the merge, the named parameters will
            take precedence and override the top level json keys. (templated)
            For more information about templating see :ref:`jinja-templating`.
            https://docs.databricks.com/api/latest/jobs.html#runs-submit
        - spark_jar_task (dict, optional): The main class and parameters for the JAR task. Note that
            the actual JAR is specified in the `libraries`.
            *EITHER* `spark_jar_task` *OR* `notebook_task` should be specified.
            This field will be templated.
            https://docs.databricks.com/api/latest/jobs.html#jobssparkjartask
        - notebook_task (dict, optional): The notebook path and parameters for the notebook task.
            *EITHER* `spark_jar_task` *OR* `notebook_task` should be specified.
            This field will be templated.
            https://docs.databricks.com/api/latest/jobs.html#jobsnotebooktask
        - new_cluster (dict, optional): Specs for a new cluster on which this task will be run.
            *EITHER* `new_cluster` *OR* `existing_cluster_id` should be specified.
            This field will be templated.
            https://docs.databricks.com/api/latest/jobs.html#jobsclusterspecnewcluster
        - existing_cluster_id (str, optional): ID for existing cluster on which to run this task.
            *EITHER* `new_cluster` *OR* `existing_cluster_id` should be specified.
            This field will be templated.
        - libraries (list of dicts, optional): Libraries which this run will use.
            This field will be templated.
            https://docs.databricks.com/api/latest/libraries.html#managedlibrarieslibrary
        - run_name (str, optional): The run name used for this task.
            By default this will be set to the Prefect `task_id`. This `task_id` is a
            required parameter of the superclass `Task`.
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
            - run_id (str): Run id of the submitted run
        """

        assert (
            databricks_conn_secret
        ), "A databricks connection string must be supplied as a dictionary or through Prefect Secrets"
        assert isinstance(
            databricks_conn_secret, dict
        ), "`databricks_conn_secret` must be supplied as a valid dictionary."

        # Initialize Databricks Connections
        hook = self.get_hook()

        if spark_jar_task is not None:
            self.json["spark_jar_task"] = spark_jar_task
        if notebook_task is not None:
            self.json["notebook_task"] = notebook_task
        if new_cluster is not None:
            self.json["new_cluster"] = new_cluster
        if existing_cluster_id is not None:
            self.json["existing_cluster_id"] = existing_cluster_id
        if libraries is not None:
            self.json["libraries"] = libraries
        if run_name is not None:
            self.json["run_name"] = run_name
        if timeout_seconds is not None:
            self.json["timeout_seconds"] = timeout_seconds
        if "run_name" not in self.json:
            self.json["run_name"] = run_name or "Run Submitted by Prefect"

        # Validate the dictionary to a valid JSON object
        self.json = _deep_string_coerce(self.json)

        # Submit the job
        self.run_id = hook.submit_run(self.json)
        _handle_databricks_task_execution(self, hook, self.logger)

        return self.run_id


class DatabricksRunNow(Task):
    """
    Runs an existing Spark job run to Databricks using the
    `api/2.0/jobs/run-now
    <https://docs.databricks.com/api/latest/jobs.html#run-now>`_
    API endpoint.

    There are two ways to instantiate this task.

    In the first way, you can take the JSON payload that you typically use
    to call the `api/2.0/jobs/run-now` endpoint and pass it directly
    to our `DatabricksRunNow` task through the `json` parameter.
    For example:

    ```
    json = {
          "job_id": 42,
          "notebook_params": {
            "dry-run": "true",
            "oldest-time-to-consider": "1457570074236"
          }
        }

    conn = PrefectSecret('DATABRICKS_CONNECTION_STRING')
    notebook_run = DatabricksRunNow(databricks_conn_string=conn, json=json)
    ```

    Another way to accomplish the same thing is to use the named parameters
    of the `DatabricksRunNow` task directly. Note that there is exactly
    one named parameter for each top level parameter in the `run-now`
    endpoint. In this method, your code would look like this:

    ```
    job_id=42

    notebook_params = {
        "dry-run": "true",
        "oldest-time-to-consider": "1457570074236"
    }

    python_params = ["douglas adams", "42"]

    spark_submit_params = ["--class", "org.apache.spark.examples.SparkPi"]

    conn = PrefectSecret('DATABRICKS_CONNECTION_STRING')
    notebook_run = DatabricksRunNow(
        databricks_conn_string=conn,
        notebook_params=notebook_params,
        python_params=python_params,
        spark_submit_params=spark_submit_params
    )
    ```

    In the case where both the json parameter **AND** the named parameters
    are provided, they will be merged together. If there are conflicts during the merge,
    the named parameters will take precedence and override the top level `json` keys.

    This task requires a Databricks connection to be specified as a Prefect secret and can
    be passed to the task like so:

    ```
    from prefect.tasks.secrets import PrefectSecret
    from prefect.contrib.tasks.databricks import DatabricksRunNow

    with Flow('my flow') as flow:
        conn = PrefectSecret('DATABRICKS_CONNECTION_STRING')
        DatabricksRunNow(databricks_conn_string=conn, json=...)
    ```

    Currently the named parameters that `DatabricksRunNow` task supports are

    - `job_id`
    - `json`
    - `notebook_params`
    - `python_params`
    - `spark_submit_params`

    Args:
        - databricks_conn_secret (dict, optional): Dictionary representation of the Databricks Connection
            String. Structure must be a string of valid JSON. To use token based authentication, provide
            the key `token` in the string for the connection and create the key `host`.
            `PREFECT__CONTEXT__SECRETS__DATABRICKS_CONNECTION_STRING=
            '{"host": "abcdef.xyz", "login": "ghijklmn", "password": "opqrst"}'`
            OR
            `PREFECT__CONTEXT__SECRETS__DATABRICKS_CONNECTION_STRING=
            '{"host": "abcdef.xyz", "token": "ghijklmn"}'`
            See documentation of the `DatabricksSubmitRun` Task to see how to pass in the connection
            string using `PrefectSecret`.
        - job_id (str, optional): The job_id of the existing Databricks job.
            https://docs.databricks.com/api/latest/jobs.html#run-now
        - json (dict, optional): A JSON object containing API parameters which will be passed
            directly to the `api/2.0/jobs/run-now` endpoint. The other named parameters
            (i.e. `notebook_params`, `spark_submit_params`..) to this operator will
            be merged with this json dictionary if they are provided.
            If there are conflicts during the merge, the named parameters will
            take precedence and override the top level json keys. (templated)
            https://docs.databricks.com/api/latest/jobs.html#run-now
        - notebook_params (dict, optional): A dict from keys to values for jobs with notebook task,
            e.g. "notebook_params": {"name": "john doe", "age":  "35"}.
            The map is passed to the notebook and will be accessible through the
            dbutils.widgets.get function. See Widgets for more information.
            If not specified upon run-now, the triggered run will use the
            job’s base parameters. notebook_params cannot be
            specified in conjunction with jar_params. The json representation
            of this field (i.e. {"notebook_params":{"name":"john doe","age":"35"}})
            cannot exceed 10,000 bytes.
            https://docs.databricks.com/user-guide/notebooks/widgets.html
        - python_params (list[str], optional): A list of parameters for jobs with python tasks,
            e.g. "python_params": ["john doe", "35"].
            The parameters will be passed to python file as command line parameters.
            If specified upon run-now, it would overwrite the parameters specified in
            job setting.
            The json representation of this field (i.e. {"python_params":["john doe","35"]})
            cannot exceed 10,000 bytes.
            https://docs.databricks.com/api/latest/jobs.html#run-now
        - spark_submit_params (list[str], optional): A list of parameters for jobs with spark submit
            task, e.g. "spark_submit_params": ["--class", "org.apache.spark.examples.SparkPi"].
            The parameters will be passed to spark-submit script as command line parameters.
            If specified upon run-now, it would overwrite the parameters specified
            in job setting.
            The json representation of this field cannot exceed 10,000 bytes.
            https://docs.databricks.com/api/latest/jobs.html#run-now
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
        databricks_conn_secret: dict = None,
        job_id: str = None,
        json: dict = None,
        notebook_params: dict = None,
        python_params: List[str] = None,
        spark_submit_params: List[str] = None,
        polling_period_seconds: int = 30,
        databricks_retry_limit: int = 3,
        databricks_retry_delay: float = 1,
        **kwargs
    ) -> None:

        self.databricks_conn_secret = databricks_conn_secret
        self.json = json or {}
        self.notebook_params = notebook_params
        self.python_params = python_params
        self.spark_submit_params = spark_submit_params
        self.polling_period_seconds = polling_period_seconds
        self.databricks_retry_limit = databricks_retry_limit
        self.databricks_retry_delay = databricks_retry_delay

        self.run_id = None

        super().__init__(**kwargs)

    def get_hook(self):
        return DatabricksHook(
            self.databricks_conn_secret,
            retry_limit=self.databricks_retry_limit,
            retry_delay=self.databricks_retry_delay,
        )

    @defaults_from_attrs(
        "databricks_conn_secret",
        "job_id",
        "json",
        "notebook_params",
        "python_params",
        "spark_submit_params",
        "polling_period_seconds",
        "databricks_retry_limit",
        "databricks_retry_delay",
    )
    def run(
        self,
        databricks_conn_secret: dict = None,
        job_id: str = None,
        json: dict = None,
        notebook_params: dict = None,
        python_params: List[str] = None,
        spark_submit_params: List[str] = None,
        polling_period_seconds: int = 30,
        databricks_retry_limit: int = 3,
        databricks_retry_delay: float = 1,
    ) -> str:
        """
        Task run method.

        Args:

            - databricks_conn_secret (dict, optional): Dictionary representation of the Databricks
                Connection String. Structure must be a string of valid JSON. To use token based
                authentication, provide the key `token` in the string for the connection and create the
                key `host`.
                `PREFECT__CONTEXT__SECRETS__DATABRICKS_CONNECTION_STRING=
                '{"host": "abcdef.xyz", "login": "ghijklmn", "password": "opqrst"}'`
                OR
                `PREFECT__CONTEXT__SECRETS__DATABRICKS_CONNECTION_STRING=
                '{"host": "abcdef.xyz", "token": "ghijklmn"}'`
                See documentation of the `DatabricksSubmitRun` Task to see how to pass in the connection
                string using `PrefectSecret`.
            - job_id (str, optional): The job_id of the existing Databricks job.
                https://docs.databricks.com/api/latest/jobs.html#run-now
            - json (dict, optional): A JSON object containing API parameters which will be passed
                directly to the `api/2.0/jobs/run-now` endpoint. The other named parameters
                (i.e. `notebook_params`, `spark_submit_params`..) to this operator will
                be merged with this json dictionary if they are provided.
                If there are conflicts during the merge, the named parameters will
                take precedence and override the top level json keys. (templated)
                https://docs.databricks.com/api/latest/jobs.html#run-now
            - notebook_params (dict, optional): A dict from keys to values for jobs with notebook task,
                e.g. "notebook_params": {"name": "john doe", "age":  "35"}.
                The map is passed to the notebook and will be accessible through the
                dbutils.widgets.get function. See Widgets for more information.
                If not specified upon run-now, the triggered run will use the
                job’s base parameters. notebook_params cannot be
                specified in conjunction with jar_params. The json representation
                of this field (i.e. {"notebook_params":{"name":"john doe","age":"35"}})
                cannot exceed 10,000 bytes.
                https://docs.databricks.com/user-guide/notebooks/widgets.html
            - python_params (list[str], optional): A list of parameters for jobs with python tasks,
                e.g. "python_params": ["john doe", "35"].
                The parameters will be passed to python file as command line parameters.
                If specified upon run-now, it would overwrite the parameters specified in
                job setting.
                The json representation of this field (i.e. {"python_params":["john doe","35"]})
                cannot exceed 10,000 bytes.
                https://docs.databricks.com/api/latest/jobs.html#run-now
            - spark_submit_params (list[str], optional): A list of parameters for jobs with spark submit
                task, e.g. "spark_submit_params": ["--class", "org.apache.spark.examples.SparkPi"].
                The parameters will be passed to spark-submit script as command line parameters.
                If specified upon run-now, it would overwrite the parameters specified
                in job setting.
                The json representation of this field cannot exceed 10,000 bytes.
                https://docs.databricks.com/api/latest/jobs.html#run-now
            - polling_period_seconds (int, optional): Controls the rate which we poll for the result of
                this run. By default the task will poll every 30 seconds.
            - databricks_retry_limit (int, optional): Amount of times retry if the Databricks backend is
                unreachable. Its value must be greater than or equal to 1.
            - databricks_retry_delay (float, optional): Number of seconds to wait between retries (it
                might be a floating point number).

        Returns:
            - run_id (str): Run id of the submitted run
        """

        assert (
            databricks_conn_secret
        ), "A databricks connection string must be supplied as a dictionary or through Prefect Secrets"
        assert isinstance(
            databricks_conn_secret, dict
        ), "`databricks_conn_secret` must be supplied as a valid dictionary."

        # Initialize Databricks Connections
        hook = self.get_hook()

        if self.job_id is not None:
            self.json["job_id"] = self.job_id
        if self.notebook_params is not None:
            self.json["notebook_params"] = self.notebook_params
        if self.python_params is not None:
            self.json["python_params"] = self.python_params
        if self.spark_submit_params is not None:
            self.json["spark_submit_params"] = self.spark_submit_params

        # Validate the dictionary to a valid JSON object
        self.json = _deep_string_coerce(self.json)

        # Submit the job
        self.run_id = hook.run_now(self.json)
        _handle_databricks_task_execution(self, hook, self.logger)

        return self.run_id
