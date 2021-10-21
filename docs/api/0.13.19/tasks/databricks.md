---
sidebarDepth: 2
editLink: false
---
# Databricks Tasks
---
This module contains a collection of tasks for interacting with Databricks resources.
 ## DatabricksSubmitRun
 <div class='class-sig' id='prefect-tasks-databricks-databricks-submitjob-databrickssubmitrun'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.databricks.databricks_submitjob.DatabricksSubmitRun</p>(databricks_conn_secret=None, json=None, spark_jar_task=None, notebook_task=None, new_cluster=None, existing_cluster_id=None, libraries=None, run_name=None, timeout_seconds=None, polling_period_seconds=30, databricks_retry_limit=3, databricks_retry_delay=1, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/databricks/databricks_submitjob.py#L76">[source]</a></span></div>

Submits a Spark job run to Databricks using the `api/2.0/jobs/runs/submit <https://docs.databricks.com/api/latest/jobs.html#runs-submit>`_ API endpoint.

There are two ways to instantiate this task.

In the first way, you can take the JSON payload that you typically use to call the `api/2.0/jobs/runs/submit` endpoint and pass it directly to our `DatabricksSubmitRun` task through the `json` parameter. For example:


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

Another way to accomplish the same thing is to use the named parameters of the `DatabricksSubmitRun` directly. Note that there is exactly one named parameter for each top level parameter in the `runs/submit` endpoint. In this method, your code would look like this:


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

In the case where both the json parameter **AND** the named parameters are provided, they will be merged together. If there are conflicts during the merge, the named parameters will take precedence and override the top level `json` keys.

This task requires a Databricks connection to be specified as a Prefect secret and can be passed to the task like so:


```
from prefect.tasks.secrets import PrefectSecret
from prefect.contrib.tasks.databricks import DatabricksSubmitRun

with Flow('my flow') as flow:
    conn = PrefectSecret('DATABRICKS_CONNECTION_STRING')
    DatabricksSubmitRun(databricks_conn_string=conn, json=...)

```

Currently the named parameters that `DatabricksSubmitRun` task supports are

- `spark_jar_task` - `notebook_task` - `new_cluster` - `existing_cluster_id` - `libraries` - `run_name` - `timeout_seconds`

**Args**:     <ul class="args"><li class="args">`databricks_conn_secret (dict, optional)`: Dictionary representation of the Databricks Connection         String. Structure must be a string of valid JSON. To use token based authentication, provide         the key `token` in the string for the connection and create the key `host`.         `PREFECT__CONTEXT__SECRETS__DATABRICKS_CONNECTION_STRING=         '{"host": "abcdef.xyz", "login": "ghijklmn", "password": "opqrst"}'`         OR         `PREFECT__CONTEXT__SECRETS__DATABRICKS_CONNECTION_STRING=         '{"host": "abcdef.xyz", "token": "ghijklmn"}'`         See documentation of the `DatabricksSubmitRun` Task to see how to pass in the connection         string using `PrefectSecret`.     </li><li class="args">`json (dict, optional)`: A JSON object containing API parameters which will be passed         directly to the `api/2.0/jobs/runs/submit` endpoint. The other named parameters         (i.e. `spark_jar_task`, `notebook_task`..) to this task will         be merged with this json dictionary if they are provided.         If there are conflicts during the merge, the named parameters will         take precedence and override the top level json keys. (templated)         For more information about templating see :ref:`jinja-templating`.         https://docs.databricks.com/api/latest/jobs.html#runs-submit     </li><li class="args">`spark_jar_task (dict, optional)`: The main class and parameters for the JAR task. Note that         the actual JAR is specified in the `libraries`.         *EITHER* `spark_jar_task` *OR* `notebook_task` should be specified.         This field will be templated.         https://docs.databricks.com/api/latest/jobs.html#jobssparkjartask     </li><li class="args">`notebook_task (dict, optional)`: The notebook path and parameters for the notebook task.         *EITHER* `spark_jar_task` *OR* `notebook_task` should be specified.         This field will be templated.         https://docs.databricks.com/api/latest/jobs.html#jobsnotebooktask     </li><li class="args">`new_cluster (dict, optional)`: Specs for a new cluster on which this task will be run.         *EITHER* `new_cluster` *OR* `existing_cluster_id` should be specified.         This field will be templated.         https://docs.databricks.com/api/latest/jobs.html#jobsclusterspecnewcluster     </li><li class="args">`existing_cluster_id (str, optional)`: ID for existing cluster on which to run this task.         *EITHER* `new_cluster` *OR* `existing_cluster_id` should be specified.         This field will be templated.     </li><li class="args">`libraries (list of dicts, optional)`: Libraries which this run will use.         This field will be templated.         https://docs.databricks.com/api/latest/libraries.html#managedlibrarieslibrary     </li><li class="args">`run_name (str, optional)`: The run name used for this task.         By default this will be set to the Prefect `task_id`. This `task_id` is a         required parameter of the superclass `Task`.         This field will be templated.     </li><li class="args">`timeout_seconds (int, optional)`: The timeout for this run. By default a value of 0 is used         which means to have no timeout.         This field will be templated.     </li><li class="args">`polling_period_seconds (int, optional)`: Controls the rate which we poll for the result of         this run. By default the task will poll every 30 seconds.     </li><li class="args">`databricks_retry_limit (int, optional)`: Amount of times retry if the Databricks backend is         unreachable. Its value must be greater than or equal to 1.     </li><li class="args">`databricks_retry_delay (float, optional)`: Number of seconds to wait between retries (it         might be a floating point number).     </li><li class="args">`**kwargs (dict, optional)`: additional keyword arguments to pass to the         Task constructor</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-databricks-databricks-submitjob-databrickssubmitrun-get-hook'><p class="prefect-class">prefect.tasks.databricks.databricks_submitjob.DatabricksSubmitRun.get_hook</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/databricks/databricks_submitjob.py#L241">[source]</a></span></div>
<p class="methods"></p>|
 | <div class='method-sig' id='prefect-tasks-databricks-databricks-submitjob-databrickssubmitrun-run'><p class="prefect-class">prefect.tasks.databricks.databricks_submitjob.DatabricksSubmitRun.run</p>(databricks_conn_secret=None, json=None, spark_jar_task=None, notebook_task=None, new_cluster=None, existing_cluster_id=None, libraries=None, run_name=None, timeout_seconds=None, polling_period_seconds=30, databricks_retry_limit=3, databricks_retry_delay=1)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/databricks/databricks_submitjob.py#L248">[source]</a></span></div>
<p class="methods">Task run method.<br><br>**Args**:<br><br><ul class="args"><li class="args">`databricks_conn_secret (dict, optional)`: Dictionary representation of the Databricks Connection     String. Structure must be a string of valid JSON. To use token based authentication, provide     the key `token` in the string for the connection and create the key `host`.     `PREFECT__CONTEXT__SECRETS__DATABRICKS_CONNECTION_STRING=     '{"host": "abcdef.xyz", "login": "ghijklmn", "password": "opqrst"}'`     OR     `PREFECT__CONTEXT__SECRETS__DATABRICKS_CONNECTION_STRING=     '{"host": "abcdef.xyz", "token": "ghijklmn"}'`     See documentation of the `DatabricksSubmitRun` Task to see how to pass in the connection     string using `PrefectSecret`. </li><li class="args">`json (dict, optional)`: A JSON object containing API parameters which will be passed     directly to the `api/2.0/jobs/runs/submit` endpoint. The other named parameters     (i.e. `spark_jar_task`, `notebook_task`..) to this task will     be merged with this json dictionary if they are provided.     If there are conflicts during the merge, the named parameters will     take precedence and override the top level json keys. (templated)     For more information about templating see :ref:`jinja-templating`.     https://docs.databricks.com/api/latest/jobs.html#runs-submit </li><li class="args">`spark_jar_task (dict, optional)`: The main class and parameters for the JAR task. Note that     the actual JAR is specified in the `libraries`.     *EITHER* `spark_jar_task` *OR* `notebook_task` should be specified.     This field will be templated.     https://docs.databricks.com/api/latest/jobs.html#jobssparkjartask </li><li class="args">`notebook_task (dict, optional)`: The notebook path and parameters for the notebook task.     *EITHER* `spark_jar_task` *OR* `notebook_task` should be specified.     This field will be templated.     https://docs.databricks.com/api/latest/jobs.html#jobsnotebooktask </li><li class="args">`new_cluster (dict, optional)`: Specs for a new cluster on which this task will be run.     *EITHER* `new_cluster` *OR* `existing_cluster_id` should be specified.     This field will be templated.     https://docs.databricks.com/api/latest/jobs.html#jobsclusterspecnewcluster </li><li class="args">`existing_cluster_id (str, optional)`: ID for existing cluster on which to run this task.     *EITHER* `new_cluster` *OR* `existing_cluster_id` should be specified.     This field will be templated. </li><li class="args">`libraries (list of dicts, optional)`: Libraries which this run will use.     This field will be templated.     https://docs.databricks.com/api/latest/libraries.html#managedlibrarieslibrary </li><li class="args">`run_name (str, optional)`: The run name used for this task.     By default this will be set to the Prefect `task_id`. This `task_id` is a     required parameter of the superclass `Task`.     This field will be templated. </li><li class="args">`timeout_seconds (int, optional)`: The timeout for this run. By default a value of 0 is used     which means to have no timeout.     This field will be templated. </li><li class="args">`polling_period_seconds (int, optional)`: Controls the rate which we poll for the result of     this run. By default the task will poll every 30 seconds. </li><li class="args">`databricks_retry_limit (int, optional)`: Amount of times retry if the Databricks backend is     unreachable. Its value must be greater than or equal to 1. </li><li class="args">`databricks_retry_delay (float, optional)`: Number of seconds to wait between retries (it     might be a floating point number).</li></ul> **Returns**:     <ul class="args"><li class="args">`run_id (str)`: Run id of the submitted run</li></ul></p>|

---
<br>

 ## DatabricksRunNow
 <div class='class-sig' id='prefect-tasks-databricks-databricks-submitjob-databricksrunnow'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.databricks.databricks_submitjob.DatabricksRunNow</p>(databricks_conn_secret=None, job_id=None, json=None, notebook_params=None, python_params=None, spark_submit_params=None, polling_period_seconds=30, databricks_retry_limit=3, databricks_retry_delay=1, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/databricks/databricks_submitjob.py#L374">[source]</a></span></div>

Runs an existing Spark job run to Databricks using the `api/2.0/jobs/run-now <https://docs.databricks.com/api/latest/jobs.html#run-now>`_ API endpoint.

There are two ways to instantiate this task.

In the first way, you can take the JSON payload that you typically use to call the `api/2.0/jobs/run-now` endpoint and pass it directly to our `DatabricksRunNow` task through the `json` parameter. For example:


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

Another way to accomplish the same thing is to use the named parameters of the `DatabricksRunNow` task directly. Note that there is exactly one named parameter for each top level parameter in the `run-now` endpoint. In this method, your code would look like this:


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

In the case where both the json parameter **AND** the named parameters are provided, they will be merged together. If there are conflicts during the merge, the named parameters will take precedence and override the top level `json` keys.

This task requires a Databricks connection to be specified as a Prefect secret and can be passed to the task like so:


```
from prefect.tasks.secrets import PrefectSecret
from prefect.contrib.tasks.databricks import DatabricksRunNow

with Flow('my flow') as flow:
    conn = PrefectSecret('DATABRICKS_CONNECTION_STRING')
    DatabricksRunNow(databricks_conn_string=conn, json=...)

```

Currently the named parameters that `DatabricksRunNow` task supports are

- `job_id` - `json` - `notebook_params` - `python_params` - `spark_submit_params`

**Args**:     <ul class="args"><li class="args">`databricks_conn_secret (dict, optional)`: Dictionary representation of the Databricks Connection         String. Structure must be a string of valid JSON. To use token based authentication, provide         the key `token` in the string for the connection and create the key `host`.         `PREFECT__CONTEXT__SECRETS__DATABRICKS_CONNECTION_STRING=         '{"host": "abcdef.xyz", "login": "ghijklmn", "password": "opqrst"}'`         OR         `PREFECT__CONTEXT__SECRETS__DATABRICKS_CONNECTION_STRING=         '{"host": "abcdef.xyz", "token": "ghijklmn"}'`         See documentation of the `DatabricksSubmitRun` Task to see how to pass in the connection         string using `PrefectSecret`.     </li><li class="args">`job_id (str, optional)`: The job_id of the existing Databricks job.         https://docs.databricks.com/api/latest/jobs.html#run-now     </li><li class="args">`json (dict, optional)`: A JSON object containing API parameters which will be passed         directly to the `api/2.0/jobs/run-now` endpoint. The other named parameters         (i.e. `notebook_params`, `spark_submit_params`..) to this operator will         be merged with this json dictionary if they are provided.         If there are conflicts during the merge, the named parameters will         take precedence and override the top level json keys. (templated)         https://docs.databricks.com/api/latest/jobs.html#run-now     </li><li class="args">`notebook_params (dict, optional)`: A dict from keys to values for jobs with notebook task,         e.g. "notebook_params": {"name": "john doe", "age":  "35"}.         The map is passed to the notebook and will be accessible through the         dbutils.widgets.get function. See Widgets for more information.         If not specified upon run-now, the triggered run will use the         job’s base parameters. notebook_params cannot be         specified in conjunction with jar_params. The json representation         of this field (i.e. {"notebook_params":{"name":"john doe","age":"35"}})         cannot exceed 10,000 bytes.         https://docs.databricks.com/user-guide/notebooks/widgets.html     </li><li class="args">`python_params (list[str], optional)`: A list of parameters for jobs with python tasks,         e.g. "python_params": ["john doe", "35"].         The parameters will be passed to python file as command line parameters.         If specified upon run-now, it would overwrite the parameters specified in         job setting.         The json representation of this field (i.e. {"python_params":["john doe","35"]})         cannot exceed 10,000 bytes.         https://docs.databricks.com/api/latest/jobs.html#run-now     </li><li class="args">`spark_submit_params (list[str], optional)`: A list of parameters for jobs with spark submit         task, e.g. "spark_submit_params": ["--class", "org.apache.spark.examples.SparkPi"].         The parameters will be passed to spark-submit script as command line parameters.         If specified upon run-now, it would overwrite the parameters specified         in job setting.         The json representation of this field cannot exceed 10,000 bytes.         https://docs.databricks.com/api/latest/jobs.html#run-now     </li><li class="args">`timeout_seconds (int, optional)`: The timeout for this run. By default a value of 0 is used         which means to have no timeout.         This field will be templated.     </li><li class="args">`polling_period_seconds (int, optional)`: Controls the rate which we poll for the result of         this run. By default the task will poll every 30 seconds.     </li><li class="args">`databricks_retry_limit (int, optional)`: Amount of times retry if the Databricks backend is         unreachable. Its value must be greater than or equal to 1.     </li><li class="args">`databricks_retry_delay (float, optional)`: Number of seconds to wait between retries (it         might be a floating point number).     </li><li class="args">`**kwargs (dict, optional)`: additional keyword arguments to pass to the         Task constructor</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-databricks-databricks-submitjob-databricksrunnow-get-hook'><p class="prefect-class">prefect.tasks.databricks.databricks_submitjob.DatabricksRunNow.get_hook</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/databricks/databricks_submitjob.py#L536">[source]</a></span></div>
<p class="methods"></p>|
 | <div class='method-sig' id='prefect-tasks-databricks-databricks-submitjob-databricksrunnow-run'><p class="prefect-class">prefect.tasks.databricks.databricks_submitjob.DatabricksRunNow.run</p>(databricks_conn_secret=None, job_id=None, json=None, notebook_params=None, python_params=None, spark_submit_params=None, polling_period_seconds=30, databricks_retry_limit=3, databricks_retry_delay=1)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/databricks/databricks_submitjob.py#L543">[source]</a></span></div>
<p class="methods">Task run method.<br><br>**Args**:<br><br><ul class="args"><li class="args">`databricks_conn_secret (dict, optional)`: Dictionary representation of the Databricks         Connection String. Structure must be a string of valid JSON. To use token based         authentication, provide the key `token` in the string for the connection and create the         key `host`.         `PREFECT__CONTEXT__SECRETS__DATABRICKS_CONNECTION_STRING=         '{"host": "abcdef.xyz", "login": "ghijklmn", "password": "opqrst"}'`         OR         `PREFECT__CONTEXT__SECRETS__DATABRICKS_CONNECTION_STRING=         '{"host": "abcdef.xyz", "token": "ghijklmn"}'`         See documentation of the `DatabricksSubmitRun` Task to see how to pass in the connection         string using `PrefectSecret`.     </li><li class="args">`job_id (str, optional)`: The job_id of the existing Databricks job.         https://docs.databricks.com/api/latest/jobs.html#run-now     </li><li class="args">`json (dict, optional)`: A JSON object containing API parameters which will be passed         directly to the `api/2.0/jobs/run-now` endpoint. The other named parameters         (i.e. `notebook_params`, `spark_submit_params`..) to this operator will         be merged with this json dictionary if they are provided.         If there are conflicts during the merge, the named parameters will         take precedence and override the top level json keys. (templated)         https://docs.databricks.com/api/latest/jobs.html#run-now     </li><li class="args">`notebook_params (dict, optional)`: A dict from keys to values for jobs with notebook task,         e.g. "notebook_params": {"name": "john doe", "age":  "35"}.         The map is passed to the notebook and will be accessible through the         dbutils.widgets.get function. See Widgets for more information.         If not specified upon run-now, the triggered run will use the         job’s base parameters. notebook_params cannot be         specified in conjunction with jar_params. The json representation         of this field (i.e. {"notebook_params":{"name":"john doe","age":"35"}})         cannot exceed 10,000 bytes.         https://docs.databricks.com/user-guide/notebooks/widgets.html     </li><li class="args">`python_params (list[str], optional)`: A list of parameters for jobs with python tasks,         e.g. "python_params": ["john doe", "35"].         The parameters will be passed to python file as command line parameters.         If specified upon run-now, it would overwrite the parameters specified in         job setting.         The json representation of this field (i.e. {"python_params":["john doe","35"]})         cannot exceed 10,000 bytes.         https://docs.databricks.com/api/latest/jobs.html#run-now     </li><li class="args">`spark_submit_params (list[str], optional)`: A list of parameters for jobs with spark submit         task, e.g. "spark_submit_params": ["--class", "org.apache.spark.examples.SparkPi"].         The parameters will be passed to spark-submit script as command line parameters.         If specified upon run-now, it would overwrite the parameters specified         in job setting.         The json representation of this field cannot exceed 10,000 bytes.         https://docs.databricks.com/api/latest/jobs.html#run-now     </li><li class="args">`polling_period_seconds (int, optional)`: Controls the rate which we poll for the result of         this run. By default the task will poll every 30 seconds.     </li><li class="args">`databricks_retry_limit (int, optional)`: Amount of times retry if the Databricks backend is         unreachable. Its value must be greater than or equal to 1.     </li><li class="args">`databricks_retry_delay (float, optional)`: Number of seconds to wait between retries (it         might be a floating point number).</li></ul> **Returns**:     <ul class="args"><li class="args">`run_id (str)`: Run id of the submitted run</li></ul></p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on December 16, 2020 at 21:36 UTC</p>