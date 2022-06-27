---
sidebarDepth: 2
editLink: false
---
# DBT Tasks

!!! tip Verified by Prefect
<div class="verified-task">
<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 48 48" fill="none">
<circle cx="24" cy="24" r="24" fill="#42b983"/>
<circle cx="24" cy="24" r="9" stroke="#fff" stroke-width="2"/>
<path d="M19 24L22.4375 27L29 20.5" stroke="#fff" stroke-width="2"/>
</svg>
<div>
    These tasks have been tested and verified by Prefect.
</div>
</div>

---

This module contains a task for interacting with dbt via the shell.
 ## DbtShellTask
 <div class='class-sig' id='prefect-tasks-dbt-dbt-dbtshelltask'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.dbt.dbt.DbtShellTask</p>(command=None, profile_name=None, env=None, environment=None, overwrite_profiles=False, profiles_dir=None, set_profiles_envar=True, dbt_kwargs=None, helper_script=None, shell=&quot;bash&quot;, return_all=False, log_stderr=False, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/dbt/dbt.py#L19">[source]</a></span></div>

Task for running dbt commands. It will create a profiles.yml file prior to running dbt commands.

This task inherits all configuration options from the [ShellTask](https://docs.prefect.io/api/latest/tasks/shell.html#shelltask).

**Args**:     <ul class="args"><li class="args">`command (string, optional)`: dbt command to be executed; can also be         provided post-initialization by calling this task instance     </li><li class="args">`dbt_kwargs (dict, optional)`: keyword arguments used to populate the profiles.yml file         (e.g.  `{'type': 'snowflake', 'threads': 4, 'account': '...'}`); can also be         provided at runtime     </li><li class="args">`env (dict, optional)`: dictionary of environment variables to use for         the subprocess; can also be provided at runtime     </li><li class="args">`environment (string, optional)`: The default target your dbt project will use     </li><li class="args">`overwrite_profiles (boolean, optional)`: flag to indicate whether existing         profiles.yml file should be overwritten; defaults to `False`     </li><li class="args">`profile_name (string, optional)`: Profile name used for populating the profile name of         profiles.yml     </li><li class="args">`profiles_dir (string, optional)`: path to directory where the profile.yml file will be         contained     </li><li class="args">`set_profiles_envar (boolean, optional)`: flag to indicate whether DBT_PROFILES_DIR         should be set to the provided profiles_dir; defaults to `True`     </li><li class="args">`helper_script (str, optional)`: a string representing a shell script, which         will be executed prior to the `command` in the same process. Can be used to         change directories, define helper functions, etc. when re-using this Task         for different commands in a Flow; can also be provided at runtime     </li><li class="args">`shell (string, optional)`: shell to run the command with; defaults to "bash"     </li><li class="args">`return_all (bool, optional)`: boolean specifying whether this task should return all         lines of stdout as a list, or just the last line as a string; defaults to `False`     </li><li class="args">`log_stderr (bool, optional)`: boolean specifying whether this task         should log the output from stderr in the case of a non-zero exit code;         defaults to `False`     </li><li class="args">`**kwargs`: additional keyword arguments to pass to the Task constructor</li></ul> **Example**:     
```python
    from prefect import Flow
    from prefect.tasks.dbt import DbtShellTask

    with Flow(name="dbt_flow") as f:
        task = DbtShellTask(
            profile_name='default',
            environment='test',
            dbt_kwargs={
                'type': 'snowflake',
                'threads': 1,
                'account': 'account.us-east-1'
            },
            overwrite_profiles=True,
            profiles_dir=test_path
        )(command='dbt run')

    out = f.run()

```

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-dbt-dbt-dbtshelltask-run'><p class="prefect-class">prefect.tasks.dbt.dbt.DbtShellTask.run</p>(command=None, env=None, helper_script=None, dbt_kwargs=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/dbt/dbt.py#L110">[source]</a></span></div>
<p class="methods">If no profiles.yml file is found or if overwrite_profiles flag is set to True, this will first generate a profiles.yml file in the profiles_dir directory. Then run the dbt cli shell command.<br><br>**Args**:     <ul class="args"><li class="args">`command (string)`: shell command to be executed; can also be         provided at task initialization. Any variables / functions defined in         `self.helper_script` will be available in the same process this command         runs in     </li><li class="args">`env (dict, optional)`: dictionary of environment variables to use for         the subprocess     </li><li class="args">`helper_script (str, optional)`: a string representing a shell script, which         will be executed prior to the `command` in the same process. Can be used to         change directories, define helper functions, etc. when re-using this Task         for different commands in a Flow     </li><li class="args">`dbt_kwargs(dict, optional)`: keyword arguments used to populate the profiles.yml file</li></ul> **Returns**:     <ul class="args"><li class="args">`stdout (string)`: if `return_all` is `False` (the default), only the last line of         stdout is returned, otherwise all lines are returned, which is useful for         passing result of shell command to other downstream tasks. If there is no         output, `None` is returned.</li></ul> **Raises**:     <ul class="args"><li class="args">`prefect.engine.signals.FAIL`: if command has an exit code other         than 0</li></ul></p>|

---
<br>

 ## DbtCloudRunJob
 <div class='class-sig' id='prefect-tasks-dbt-dbt-dbtcloudrunjob'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.dbt.dbt.DbtCloudRunJob</p>(cause=None, account_id=None, job_id=None, token=None, additional_args=None, account_id_env_var_name=&quot;DBT_CLOUD_ACCOUNT_ID&quot;, job_id_env_var_name=&quot;DBT_CLOUD_JOB_ID&quot;, token_env_var_name=&quot;DBT_CLOUD_TOKEN&quot;, wait_for_job_run_completion=False, max_wait_time=None, domain=&quot;cloud.getdbt.com&quot;)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/dbt/dbt.py#L197">[source]</a></span></div>

Task for running a dbt Cloud job using dbt Cloud APIs v2. For info about dbt Cloud APIs, please refer to https://docs.getdbt.com/dbt-cloud/api-v2 Please note that this task will fail if any call to dbt Cloud APIs fails.

Running this task will generate a markdown artifact viewable in the Prefect UI. The artifact will contain links to the dbt artifacts generate as a result of the job run.

**Args**:     <ul class="args"><li class="args">`cause (string)`: A string describing the reason for triggering the job run     </li><li class="args">`account_id (int, optional)`: dbt Cloud account ID.         Can also be passed as an env var.     </li><li class="args">`job_id (int, optional)`: dbt Cloud job ID     </li><li class="args">`token (string, optional)`: dbt Cloud token.         Please note that this token must have access at least to the dbt Trigger Job API.     </li><li class="args">`additional_args (dict, optional)`: additional information to pass to the Trigger Job API.         For a list of the possible information,         have a look at: https://docs.getdbt.com/dbt-cloud/api-v2#operation/triggerRun     </li><li class="args">`account_id_env_var_name (string, optional)`:         the name of the env var that contains the dbt Cloud account ID.         Defaults to DBT_CLOUD_ACCOUNT_ID.         Used only if account_id is None.     </li><li class="args">`job_id_env_var_name (string, optional)`:         the name of the env var that contains the dbt Cloud job ID         Default to DBT_CLOUD_JOB_ID.         Used only if job_id is None.     </li><li class="args">`token_env_var_name (string, optional)`:         the name of the env var that contains the dbt Cloud token         Default to DBT_CLOUD_TOKEN.         Used only if token is None.     </li><li class="args">`wait_for_job_run_completion (boolean, optional)`:         Whether the task should wait for the job run completion or not.         Default to False.     </li><li class="args">`max_wait_time (int, optional)`: The number of seconds to wait for the dbt Cloud         job to finish.         Used only if wait_for_job_run_completion = True.     </li><li class="args">`domain (str, optional)`: Custom domain for API call. Defaults to `cloud.getdbt.com`.</li></ul> **Returns**:     <ul class="args"></ul>       if wait_for_job_run_completion = True, then returns the get job result.         The get job result is the dict under the "data" key.         Have a look at the Response section at:         https://docs.getdbt.com/dbt-cloud/api-v2#operation/getRunById**Raises**:     <ul class="args"><li class="args">`prefect.engine.signals.FAIL`: whether there's a HTTP status code != 200         and also whether the run job result has a status != 10 AND "finished_at" is not None         Have a look at the status codes at:         https://docs.getdbt.com/dbt-cloud/api-v2#operation/getRunById</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-dbt-dbt-dbtcloudrunjob-run'><p class="prefect-class">prefect.tasks.dbt.dbt.DbtCloudRunJob.run</p>(cause=None, account_id=None, job_id=None, token=None, additional_args=None, account_id_env_var_name=&quot;ACCOUNT_ID&quot;, job_id_env_var_name=&quot;JOB_ID&quot;, token_env_var_name=&quot;DBT_CLOUD_TOKEN&quot;, wait_for_job_run_completion=False, max_wait_time=None, domain=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/dbt/dbt.py#L282">[source]</a></span></div>
<p class="methods">All params available to the run method can also be passed during initialization.<br><br>**Args**:     <ul class="args"><li class="args">`cause (string)`: A string describing the reason for triggering the job run     </li><li class="args">`account_id (int, optional)`: dbt Cloud account ID.         Can also be passed as an env var.     </li><li class="args">`job_id (int, optional)`: dbt Cloud job ID     </li><li class="args">`token (string, optional)`: dbt Cloud token.         Please note that this token must have access at least to the dbt Trigger Job API.     </li><li class="args">`additional_args (dict, optional)`: additional information to pass to the Trigger Job API.         For a list of the possible information,         have a look at: https://docs.getdbt.com/dbt-cloud/api-v2#operation/triggerRun     </li><li class="args">`account_id_env_var_name (string, optional)`:         the name of the env var that contains the dbt Cloud account ID.         Defaults to DBT_CLOUD_ACCOUNT_ID.         Used only if account_id is None.     </li><li class="args">`job_id_env_var_name (string, optional)`:         the name of the env var that contains the dbt Cloud job ID         Default to DBT_CLOUD_JOB_ID.         Used only if job_id is None.     </li><li class="args">`token_env_var_name (string, optional)`:         the name of the env var that contains the dbt Cloud token         Default to DBT_CLOUD_TOKEN.         Used only if token is None.     </li><li class="args">`wait_for_job_run_completion (boolean, optional)`:         Whether the task should wait for the job run completion or not.         Default to False.     </li><li class="args">`max_wait_time (int, optional)`: The number of seconds to wait for the dbt Cloud         job to finish.         Used only if wait_for_job_run_completion = True. </li><li class="args">`domain (str, optional)`: Custom domain for API call. Defaults to `cloud.getdbt.com`.</li></ul> **Returns**:     <ul class="args"></ul>       if wait_for_job_run_completion = True, then returns the get job result.         The get job result is the dict under the "data" key. Links to the dbt artifacts are         also included under the `artifact_urls` key.         Have a look at the Response section at:         https://docs.getdbt.com/dbt-cloud/api-v2#operation/getRunById**Raises**:     <ul class="args"><li class="args">`prefect.engine.signals.FAIL`: whether there's a HTTP status code != 200         and also whether the run job result has a status != 10 AND "finished_at" is not None         Have a look at the status codes at:         https://docs.getdbt.com/dbt-cloud/api-v2#operation/getRunById</li></ul></p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on February 23, 2022 at 19:26 UTC</p>