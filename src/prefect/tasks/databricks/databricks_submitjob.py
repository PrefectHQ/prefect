import time
from enum import Enum
from typing import Any, Dict, List, Optional, Union

import six
from pydantic import parse_obj_as

import prefect
from prefect import Task
from prefect.exceptions import PrefectException
from prefect.tasks.databricks.databricks_hook import DatabricksHook
from prefect.tasks.databricks.models import (
    AccessControlRequest,
    AccessControlRequestForGroup,
    AccessControlRequestForUser,
    JobTaskSettings,
)
from prefect.utilities.tasks import defaults_from_attrs


def _deep_string_coerce(content, json_path="json"):
    """
    Coerces content or all values of content if it is a dict to a string. The
    function will throw if content contains non-string or non-numeric types.

    The reason why we have this function is because the `self.json` field must be a
    dict with only string values. This is because `render_template` will fail
    for numerical values.
    """
    if isinstance(content, six.string_types):
        return content
    elif isinstance(content, six.integer_types + (float,)):
        # Databricks can tolerate either numeric or string types in the API backend.
        return str(content)
    elif content is None:
        return content
    elif isinstance(content, (list, tuple)):
        return [
            _deep_string_coerce(content=item, json_path=f"{json_path}[{i}]")
            for i, item in enumerate(content)
        ]
    elif isinstance(content, dict):
        return {
            key: _deep_string_coerce(content=value, json_path=f"{json_path}[{key}]")
            for key, value in list(content.items())
        }
    elif isinstance(content, Enum):
        return str(content.value)
    raise ValueError(
        f"Type {type(content)} used for parameter {json_path} is not a number or a string"
    )


def _handle_databricks_task_execution(task, hook, log, submitted_run_id):
    """
    Handles the Databricks + Prefect lifecycle logic for a Databricks task

    Args:
        - task (prefect.Task) : Prefect task being handled
        - hook (prefect.tasks.databricks.databricks_hook.DatabricksHook): Databricks Hook
        - log (logger): Prefect logging instance
        - submitted_run_id (str): run ID returned after submitting or running Databricks job
    """

    log.info("Run submitted with run_id: %s", submitted_run_id)
    run_page_url = hook.get_run_page_url(submitted_run_id)

    log.info("Run submitted with config : %s", task.json)

    log.info("View run status, Spark UI, and logs at %s", run_page_url)
    while True:
        run_state = hook.get_run_state(submitted_run_id)
        if run_state.is_terminal:
            if run_state.is_successful:
                log.info("%s completed successfully.", task.name)
                log.info("View run status, Spark UI, and logs at %s", run_page_url)
                return
            else:
                error_message = "{t} failed with terminal state: {s}".format(
                    t=task.name, s=run_state
                )
                raise PrefectException(error_message)
        else:
            log.info("%s in run state: %s", task.name, run_state)
            log.info("View run status, Spark UI, and logs at %s", run_page_url)
            log.info("Sleeping for %s seconds.", task.polling_period_seconds)
            time.sleep(task.polling_period_seconds)


class DatabricksSubmitRun(Task):
    """
    Submits a Spark job run to Databricks using the
    [api/2.0/jobs/runs/submit](https://docs.databricks.com/api/latest/jobs.html#runs-submit)
    API endpoint.

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

    Examples:
        There are two ways to instantiate this task.

        In the first way, you can take the JSON payload that you typically use
        to call the `api/2.0/jobs/runs/submit` endpoint and pass it directly
        to our `DatabricksSubmitRun` task through the `json` parameter.
        ```python
        from prefect import Flow
        from prefect.tasks.secrets import PrefectSecret
        from prefect.tasks.databricks import DatabricksSubmitRun

        json = {
            'new_cluster': {
                'spark_version': '10.4.x-scala2.12',
                'num_workers': 2,
                'node_type_id': "m4.large",
                'aws_attributes': {
                    'ebs_volume_type': "GENERAL_PURPOSE_SSD",
                    'ebs_volume_count': 3,
                    'ebs_volume_size': 100,
                }
            },
            'notebook_task': {
                'notebook_path': '/Users/andrew.h@prefect.io/records',
            },
        }

        with Flow("my flow") as flow:
            conn = PrefectSecret('DATABRICKS_CONNECTION_STRING')
            notebook_run = DatabricksSubmitRun(json=json)
            notebook_run(databricks_conn_secret=conn)
        ```

        Another way to accomplish the same thing is to use the named parameters
        of the `DatabricksSubmitRun` directly. Note that there is exactly
        one named parameter for each top level parameter in the `runs/submit`
        endpoint. In this method, your code would look like this:
        ```python
        from prefect import Flow
        from prefect.tasks.secrets import PrefectSecret
        from prefect.tasks.databricks import DatabricksSubmitRun

        new_cluster = {
            'spark_version': '10.4.x-scala2.12',
            'num_workers': 2,
            'node_type_id': "m4.large",
            'aws_attributes': {
                'ebs_volume_type': "GENERAL_PURPOSE_SSD",
                'ebs_volume_count': 3,
                'ebs_volume_size': 100,
            }
        }
        notebook_task = {
            'notebook_path': '/Users/prefect@example.com/PrepareData',
        }

        with Flow("my flow") as flow:
            conn = PrefectSecret('DATABRICKS_CONNECTION_STRING')
            notebook_run = DatabricksSubmitRun(
                new_cluster=new_cluster,
                notebook_task=notebook_task)
            notebook_run(databricks_conn_secret=conn)
        ```

        In the case where both the json parameter **AND** the named parameters
        are provided, they will be merged together. If there are conflicts during the merge,
        the named parameters will take precedence and override the top level `json` keys.
        This task requires a Databricks connection to be specified as a Prefect secret and can
        be passed to the task like so:
        ```
        from prefect import Flow
        from prefect.tasks.secrets import PrefectSecret
        from prefect.tasks.databricks import DatabricksSubmitRun

        with Flow("my flow") as flow:
            conn = PrefectSecret('DATABRICKS_CONNECTION_STRING')
            notebook_run = DatabricksSubmitRun(json=...)
            notebook_run(databricks_conn_secret=conn)
        ```
    """

    def __init__(
        self,
        databricks_conn_secret: Dict[str, str] = None,
        json: Dict[str, Any] = None,
        spark_jar_task: Optional[Dict[str, Any]] = None,
        notebook_task: Optional[Dict[str, Any]] = None,
        new_cluster: Optional[Dict[str, Any]] = None,
        existing_cluster_id: Optional[str] = None,
        libraries: Optional[List[Dict[str, Any]]] = None,
        run_name: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
        polling_period_seconds: int = 30,
        databricks_retry_limit: int = 3,
        databricks_retry_delay: float = 1,
        **kwargs,
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

        super().__init__(**kwargs)

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
        databricks_conn_secret: Dict[str, str] = None,
        json: Dict[str, Any] = None,
        spark_jar_task: Optional[Dict[str, Any]] = None,
        notebook_task: Optional[Dict[str, Any]] = None,
        new_cluster: Optional[Dict[str, Any]] = None,
        existing_cluster_id: Optional[str] = None,
        libraries: Optional[List[Dict[str, Any]]] = None,
        run_name: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
        polling_period_seconds: int = 30,
        databricks_retry_limit: int = 3,
        databricks_retry_delay: float = 1,
    ) -> str:
        """
        Task run method.

        Args:
            - databricks_conn_secret (dict, optional): Dictionary representation of the Databricks
                Connection String. Structure must be a string of valid JSON. To use token based,
                authentication provide the key `token` in the string for the connection and
                create the key `host`.
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

        if databricks_conn_secret is None:
            raise ValueError(
                "A databricks connection string must be supplied as "
                "a dictionary or through Prefect Secrets"
            )
        elif not isinstance(databricks_conn_secret, dict):
            raise ValueError(
                "`databricks_conn_secret` must be supplied as a valid dictionary."
            )
        self.databricks_conn_secret = databricks_conn_secret

        if json:
            self.json = json
        if polling_period_seconds:
            self.polling_period_seconds = polling_period_seconds

        # Initialize Databricks Connections
        hook = DatabricksHook(
            databricks_conn_secret,
            retry_limit=databricks_retry_limit,
            retry_delay=databricks_retry_delay,
        )

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
        submitted_run_id = hook.submit_run(self.json)
        _handle_databricks_task_execution(self, hook, self.logger, submitted_run_id)

        return submitted_run_id


class DatabricksRunNow(Task):
    """
    Runs an existing Spark job run to Databricks using the
    [api/2.1/jobs/run-now](https://docs.databricks.com/api/latest/jobs.html#run-now)
    API endpoint.

    Currently the named parameters that `DatabricksRunNow` task supports are

    - `job_id`
    - `json`
    - `notebook_params`
    - `python_params`
    - `spark_submit_params`
    - `jar_params`

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
        - jar_params (list[str], optional): A list of parameters for jobs with JAR tasks,
            e.g. "jar_params": ["john doe", "35"]. The parameters will be used to invoke the main
            function of the main class specified in the Spark JAR task. If not specified upon
            run-now, it will default to an empty list. jar_params cannot be specified in conjunction
            with notebook_params. The JSON representation of this field (i.e.
            {"jar_params":["john doe","35"]}) cannot exceed 10,000 bytes.
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

    Examples:
        There are two ways to instantiate this task.

        In the first way, you can take the JSON payload that you typically use
        to call the `api/2.1/jobs/run-now` endpoint and pass it directly
        to our `DatabricksRunNow` task through the `json` parameter.
        ```python
        from prefect import Flow
        from prefect.tasks.secrets import PrefectSecret
        from prefect.tasks.databricks import DatabricksRunNow

        json = {
            "job_id": 42,
            "notebook_params": {
                "dry-run": "true",
                "oldest-time-to-consider": "1457570074236"
            }
        }

        with Flow("my flow") as flow:
            conn = PrefectSecret('DATABRICKS_CONNECTION_STRING')
            notebook_run = DatabricksRunNow(json=json)
            notebook_run(databricks_conn_secret=conn)
        ```

        Another way to accomplish the same thing is to use the named parameters
        of the `DatabricksRunNow` task directly. Note that there is exactly
        one named parameter for each top level parameter in the `run-now`
        endpoint. In this method, your code would look like this:
        ```python
        from prefect import Flow
        from prefect.tasks.secrets import PrefectSecret
        from prefect.tasks.databricks import DatabricksRunNow

        job_id = 42

        notebook_params = {
            "dry-run": "true",
            "oldest-time-to-consider": "1457570074236"
        }

        python_params = ["douglas adams", "42"]
        spark_submit_params = ["--class", "org.apache.spark.examples.SparkPi"]
        jar_params = ["john doe","35"]

        with Flow("my flow') as flow:
            conn = PrefectSecret('DATABRICKS_CONNECTION_STRING')
            notebook_run = DatabricksRunNow(
                notebook_params=notebook_params,
                python_params=python_params,
                spark_submit_params=spark_submit_params,
                jar_params=jar_params
            )
            notebook_run(databricks_conn_secret=conn)
        ```

        In the case where both the json parameter **AND** the named parameters
        are provided, they will be merged together. If there are conflicts during the merge,
        the named parameters will take precedence and override the top level `json` keys.

        This task requires a Databricks connection to be specified as a Prefect secret and can
        be passed to the task like so:
        ```
        from prefect import Flow
        from prefect.tasks.secrets import PrefectSecret
        from prefect.tasks.databricks import DatabricksRunNow

        with Flow("my flow") as flow:
            conn = PrefectSecret('DATABRICKS_CONNECTION_STRING')
            notebook_run = DatabricksRunNow(json=...)
            notebook_run(databricks_conn_secret=conn)
        ```

    """

    def __init__(
        self,
        databricks_conn_secret: Dict[str, str] = None,
        job_id: str = None,
        json: Dict[str, Any] = None,
        notebook_params: Optional[Dict[str, Any]] = None,
        python_params: Optional[List[str]] = None,
        spark_submit_params: Optional[List[str]] = None,
        jar_params: Optional[List[str]] = None,
        polling_period_seconds: int = 30,
        databricks_retry_limit: int = 3,
        databricks_retry_delay: float = 1,
        **kwargs,
    ) -> None:

        self.databricks_conn_secret = databricks_conn_secret
        self.json = json or {}
        self.job_id = job_id
        self.notebook_params = notebook_params
        self.python_params = python_params
        self.spark_submit_params = spark_submit_params
        self.jar_params = jar_params
        self.polling_period_seconds = polling_period_seconds
        self.databricks_retry_limit = databricks_retry_limit
        self.databricks_retry_delay = databricks_retry_delay

        super().__init__(**kwargs)

    @staticmethod
    def _get_hook(
        databricks_conn_secret, databricks_retry_limit, databricks_retry_delay
    ):
        # this is a function so it's easier to mock in testing
        return DatabricksHook(
            databricks_conn_secret,
            retry_limit=databricks_retry_limit,
            retry_delay=databricks_retry_delay,
        )

    @defaults_from_attrs(
        "databricks_conn_secret",
        "job_id",
        "json",
        "notebook_params",
        "python_params",
        "spark_submit_params",
        "jar_params",
        "polling_period_seconds",
        "databricks_retry_limit",
        "databricks_retry_delay",
    )
    def run(
        self,
        databricks_conn_secret: Dict[str, str] = None,
        job_id: str = None,
        json: Dict[str, Any] = None,
        notebook_params: Optional[Dict[str, Any]] = None,
        python_params: Optional[List[str]] = None,
        spark_submit_params: Optional[List[str]] = None,
        jar_params: Optional[List[str]] = None,
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
            - jar_params (list[str], optional): A list of parameters for jobs with JAR tasks,
                e.g. "jar_params": ["john doe", "35"]. The parameters will be used to invoke the main
                function of the main class specified in the Spark JAR task. If not specified upon
                run-now, it will default to an empty list. jar_params cannot be specified in conjunction
                with notebook_params. The JSON representation of this field (i.e.
                {"jar_params":["john doe","35"]}) cannot exceed 10,000 bytes.
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
        if databricks_conn_secret is None:
            raise ValueError(
                "A databricks connection string must be supplied as "
                "a dictionary or through Prefect Secrets"
            )
        elif not isinstance(databricks_conn_secret, dict):
            raise ValueError(
                "`databricks_conn_secret` must be supplied as a valid dictionary."
            )
        self.databricks_conn_secret = databricks_conn_secret

        # Initialize Databricks Connections
        hook = self._get_hook(
            databricks_conn_secret, databricks_retry_limit, databricks_retry_delay
        )

        run_now_json = json or {}
        # Necessary be cause `_handle_databricks_task_execution` reads
        # `polling_periods_seconds` off of the task instance
        if polling_period_seconds:
            self.polling_period_seconds = polling_period_seconds

        if job_id is not None:
            run_now_json["job_id"] = job_id
        if notebook_params is not None:
            merged = run_now_json.setdefault("notebook_params", {})
            merged.update(notebook_params)
            run_now_json["notebook_params"] = merged
        if python_params is not None:
            run_now_json["python_params"] = python_params
        if spark_submit_params is not None:
            run_now_json["spark_submit_params"] = spark_submit_params
        if jar_params is not None:
            run_now_json["jar_params"] = jar_params

        # Validate the dictionary to a valid JSON object
        self.json = _deep_string_coerce(run_now_json)

        # Submit the job
        submitted_run_id = hook.run_now(self.json)
        _handle_databricks_task_execution(self, hook, self.logger, submitted_run_id)

        return submitted_run_id


class DatabricksSubmitMultitaskRun(Task):
    """
    Creates and triggers a one-time run via the Databricks submit run API endpoint. Supports
    the execution of multiple Databricks tasks within the Databricks job run. Note: Databricks
    tasks are distinct from Prefect tasks. All tasks configured will run as a single Prefect task.

    For more information about the arguments of this task, refer to the [Databricks submit run API
    documentation](https://docs.databricks.com/dev-tools/api/latest/jobs.html#operation/JobsRunsSubmit)

    Args:
        - databricks_conn_secret (dict, optional): Dictionary representation of the Databricks Connection
            String. Structure must be a string of valid JSON. To use token based authentication, provide
            the key `token` in the string for the connection and create the key `host`.
            `PREFECT__CONTEXT__SECRETS__DATABRICKS_CONNECTION_STRING=
            '{"host": "abcdef.xyz", "login": "ghijklmn", "password": "opqrst"}'`
            OR
            `PREFECT__CONTEXT__SECRETS__DATABRICKS_CONNECTION_STRING=
            '{"host": "abcdef.xyz", "token": "ghijklmn"}'`
        - tasks (List[JobTaskSettings]): A list containing the Databricks task configuration. Should
            contain configuration for at least one task.
        - timeout_seconds (int, optional):  An optional timeout applied to each run of this job.
            The default behavior is to have no timeout.
        - run_name (str, optional): An optional name for the run.
            The default value is "Job run created by Prefect flow run {flow_run_name}".
        - idempotency_token (str, optional): An optional token that can be used to guarantee
            the idempotency of job run requests. Defaults to the flow run ID.
        - access_control_list (List[AccessControlRequest]): List of permissions to set on the job.
        - polling_period_seconds (int, optional): Controls the rate which we poll for the result of
            this run. By default the task will poll every 30 seconds.
        - databricks_retry_limit (int, optional): Amount of times retry if the Databricks backend is
            unreachable. Its value must be greater than or equal to 1.
        - databricks_retry_delay (float, optional): Number of seconds to wait between retries (it
            might be a floating point number).
        - **kwargs (dict, optional): Additional keyword arguments to pass to the
            Task constructor

    Examples:
        Trigger an ad-hoc multitask run

        ```
        from prefect import Flow
        from prefect.tasks.databricks import DatabricksSubmitMultitaskRun
        from prefect.tasks.databricks.models import (
            AccessControlRequestForUser,
            AutoScale,
            AwsAttributes,
            AwsAvailability,
            CanManage,
            JobTaskSettings,
            Library,
            NewCluster,
            NotebookTask,
            SparkJarTask,
            TaskDependency,
        )

        submit_multitask_run = DatabricksSubmitMultitaskRun(
            tasks=[
                JobTaskSettings(
                    task_key="Sessionize",
                    description="Extracts session data from events",
                    existing_cluster_id="0923-164208-meows279",
                    spark_jar_task=SparkJarTask(
                        main_class_name="com.databricks.Sessionize",
                        parameters=["--data", "dbfs:/path/to/data.json"],
                    ),
                    libraries=[Library(jar="dbfs:/mnt/databricks/Sessionize.jar")],
                    timeout_seconds=86400,
                ),
                JobTaskSettings(
                    task_key="Orders_Ingest",
                    description="Ingests order data",
                    existing_cluster_id="0923-164208-meows279",
                    spark_jar_task=SparkJarTask(
                        main_class_name="com.databricks.OrdersIngest",
                        parameters=["--data", "dbfs:/path/to/order-data.json"],
                    ),
                    libraries=[Library(jar="dbfs:/mnt/databricks/OrderIngest.jar")],
                    timeout_seconds=86400,
                ),
                JobTaskSettings(
                    task_key="Match",
                    description="Matches orders with user sessions",
                    depends_on=[
                        TaskDependency(task_key="Orders_Ingest"),
                        TaskDependency(task_key="Sessionize"),
                    ],
                    new_cluster=NewCluster(
                        spark_version="10.4.x-scala2.12",
                        node_type_id="m4.large",
                        spark_conf={"spark.speculation": True},
                        aws_attributes=AwsAttributes(
                            availability=AwsAvailability.SPOT,
                            zone_id="us-west-2a",
                            ebs_volume_type="GENERAL_PURPOSE_SSD",
                            ebs_volume_count=3,
                            ebs_volume_size=100,
                        ),
                        autoscale=AutoScale(min_workers=1, max_workers=2),
                    ),
                    notebook_task=NotebookTask(
                        notebook_path="/Users/user.name@databricks.com/Match",
                        base_parameters={"name": "John Doe", "age": "35"},
                    ),
                    timeout_seconds=86400,
                ),
            ],
            run_name="A multitask job run",
            timeout_seconds=86400,
            access_control_list=[
                AccessControlRequestForUser(
                    user_name="jsmith@example.com", permission_level=CanManage.CAN_MANAGE
                )
            ],
        )


        with Flow("my flow") as f:
            conn = PrefectSecret('DATABRICKS_CONNECTION_STRING')
            submit_multitask_run(databricks_conn_secret=conn)
        ```
    """

    def __init__(
        self,
        databricks_conn_secret: Dict[str, str] = None,
        tasks: List[JobTaskSettings] = None,
        run_name: str = None,
        timeout_seconds: int = None,
        idempotency_token: str = None,
        access_control_list: List[
            Union[AccessControlRequestForUser, AccessControlRequestForGroup]
        ] = None,
        polling_period_seconds: int = 30,
        databricks_retry_limit: int = 3,
        databricks_retry_delay: float = 1,
        **kwargs,
    ):
        self.databricks_conn_secret = databricks_conn_secret
        self.tasks = tasks
        self.run_name = run_name
        self.timeout_seconds = timeout_seconds
        self.idempotency_token = idempotency_token
        self.access_control_list = access_control_list
        self.polling_period_seconds = polling_period_seconds
        self.databricks_retry_limit = databricks_retry_limit
        self.databricks_retry_delay = databricks_retry_delay
        super().__init__(**kwargs)

    @staticmethod
    def convert_dict_to_kwargs(input: Dict[str, Any]) -> Dict[str, Any]:
        """
        Method to convert a dict that matches the structure of the Databricks API call into the required
        object types for the task input

        Args:
            - input (Dict): A dictionary representing the input to the task

        Returns:
            - A dictionary with values that match the input types of the class

        Example:
        Use a JSON-like dict as input

        ```
        from prefect import Flow
        from prefect.tasks.databricks import DatabricksSubmitMultitaskRun

        submit_multitask_run = DatabricksSubmitMultitaskRun()

        databricks_kwargs = DatabricksSubmitMultitaskRun.convert_dict_to_kwargs({
            "tasks": [
                {
                    "task_key": "Sessionize",
                    "description": "Extracts session data from events",
                    "depends_on": [],
                    "existing_cluster_id": "0923-164208-meows279",
                    "spark_jar_task": {
                        "main_class_name": "com.databricks.Sessionize",
                        "parameters": ["--data", "dbfs:/path/to/data.json"],
                    },
                    "libraries": [{"jar": "dbfs:/mnt/databricks/Sessionize.jar"}],
                    "timeout_seconds": 86400,
                },
                {
                    "task_key": "Orders_Ingest",
                    "description": "Ingests order data",
                    "depends_on": [],
                    "existing_cluster_id": "0923-164208-meows279",
                    "spark_jar_task": {
                        "main_class_name": "com.databricks.OrdersIngest",
                        "parameters": ["--data", "dbfs:/path/to/order-data.json"],
                    },
                    "libraries": [{"jar": "dbfs:/mnt/databricks/OrderIngest.jar"}],
                    "timeout_seconds": 86400,
                },
                {
                    "task_key": "Match",
                    "description": "Matches orders with user sessions",
                    "depends_on": [
                        {"task_key": "Orders_Ingest"},
                        {"task_key": "Sessionize"},
                    ],
                    "new_cluster": {
                        "spark_version": "7.3.x-scala2.12",
                        "node_type_id": "i3.xlarge",
                        "spark_conf": {"spark.speculation": True},
                        "aws_attributes": {
                            "availability": "SPOT",
                            "zone_id": "us-west-2a",
                        },
                        "autoscale": {"min_workers": 2, "max_workers": 16},
                    },
                    "notebook_task": {
                        "notebook_path": "/Users/user.name@databricks.com/Match",
                        "base_parameters": {"name": "John Doe", "age": "35"},
                    },
                    "timeout_seconds": 86400,
                },
            ],
            "run_name": "A multitask job run",
            "timeout_seconds": 86400,
            "access_control_list": [
                {
                    "user_name": "jsmith@example.com",
                    "permission_level": "CAN_MANAGE",
                }
            ],
        })

        with Flow("my flow") as f:
            conn = PrefectSecret('DATABRICKS_CONNECTION_STRING')
            submit_multitask_run(**databricks_kwargs, databricks_conn_secret=conn)
        ```
        """
        kwargs = {**input, "tasks": parse_obj_as(List[JobTaskSettings], input["tasks"])}

        if input.get("access_control_list"):
            kwargs["access_control_list"] = parse_obj_as(
                List[AccessControlRequest],
                input["access_control_list"],
            )

        return kwargs

    @defaults_from_attrs(
        "databricks_conn_secret",
        "tasks",
        "run_name",
        "timeout_seconds",
        "idempotency_token",
        "access_control_list",
        "polling_period_seconds",
        "databricks_retry_limit",
        "databricks_retry_delay",
    )
    def run(
        self,
        databricks_conn_secret: dict = None,
        tasks: List[JobTaskSettings] = None,
        run_name: str = None,
        timeout_seconds: int = None,
        idempotency_token: str = None,
        access_control_list: List[AccessControlRequest] = None,
        polling_period_seconds: int = None,
        databricks_retry_limit: int = None,
        databricks_retry_delay: float = None,
    ):
        """
        Task run method. Any values passed here will overwrite the values used when initializing the
        task.

        Args:
            - databricks_conn_secret (dict, optional): Dictionary representation of the Databricks
                Connection String. Structure must be a string of valid JSON. To use token based
                authentication, provide the key `token` in the string for the connection and create
                the key `host`. `PREFECT__CONTEXT__SECRETS__DATABRICKS_CONNECTION_STRING=
                '{"host": "abcdef.xyz", "login": "ghijklmn", "password": "opqrst"}'`
                OR
                `PREFECT__CONTEXT__SECRETS__DATABRICKS_CONNECTION_STRING=
                '{"host": "abcdef.xyz", "token": "ghijklmn"}'`
            - tasks (List[JobTaskSettings]):" A list containing the Databricks task configuration. Should
                contain configuration for at least one task.
            - timeout_seconds (int, optional):  An optional timeout applied to each run of this job.
                The default behavior is to have no timeout.
            - run_name (str, optional): An optional name for the run.
                The default value is "Job run created by Prefect flow run {flow_run_name}".
            - idempotency_token (str, optional): An optional token that can be used to guarantee
                the idempotency of job run requests. Defaults to the flow run ID.
            - access_control_list (List[AccessControlRequest]): List of permissions to set on the job.
            - polling_period_seconds (int, optional): Controls the rate which we poll for the result of
                this run. By default the task will poll every 30 seconds.
            - databricks_retry_limit (int, optional): Amount of times retry if the Databricks backend is
                unreachable. Its value must be greater than or equal to 1.
            - databricks_retry_delay (float, optional): Number of seconds to wait between retries (it
                might be a floating point number).

        Returns:
            - run_id (str): Run id of the submitted run

        """
        if databricks_conn_secret is None or not isinstance(
            databricks_conn_secret, dict
        ):
            raise ValueError(
                "Databricks connection info must be supplied as a dictionary."
            )
        if tasks is None or len(tasks) < 1:
            raise ValueError("Please supply at least one Databricks task to be run.")
        run_name = (
            run_name
            or f"Job run created by Prefect flow run {prefect.context.flow_run_name}"
        )
        # Ensures that multiple job runs are not created on retries
        idempotency_token = idempotency_token or prefect.context.flow_run_id

        # Set polling_period_seconds on task because _handle_databricks_task_execution expects it
        if polling_period_seconds:
            self.polling_period_seconds = polling_period_seconds

        databricks_client = DatabricksHook(
            databricks_conn_secret,
            retry_limit=databricks_retry_limit,
            retry_delay=databricks_retry_delay,
        )

        # Set json on task instance because _handle_databricks_task_execution expects it
        self.json = _deep_string_coerce(
            dict(
                tasks=[task.dict() for task in tasks],
                run_name=run_name,
                timeout_seconds=timeout_seconds,
                idempotency_token=idempotency_token,
                access_control_list=[
                    entry.json() for entry in access_control_list or []
                ],
            )
        )

        submitted_run_id = databricks_client.submit_multi_task_run(self.json)
        _handle_databricks_task_execution(
            self, databricks_client, self.logger, submitted_run_id
        )

        return submitted_run_id
