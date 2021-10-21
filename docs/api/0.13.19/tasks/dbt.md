---
sidebarDepth: 2
editLink: false
---
# DBT Tasks
---
This module contains a task for interacting with dbt via the shell.
 ## DbtShellTask
 <div class='class-sig' id='prefect-tasks-dbt-dbt-dbtshelltask'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.dbt.dbt.DbtShellTask</p>(command=None, profile_name=None, env=None, environment=None, overwrite_profiles=False, profiles_dir=None, set_profiles_envar=True, dbt_kwargs=None, helper_script=None, shell="bash", return_all=False, log_stderr=False, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/dbt/dbt.py#L9">[source]</a></span></div>

Task for running dbt commands. It will create a profiles.yml file prior to running dbt commands.

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
 | <div class='method-sig' id='prefect-tasks-dbt-dbt-dbtshelltask-run'><p class="prefect-class">prefect.tasks.dbt.dbt.DbtShellTask.run</p>(command=None, env=None, helper_script=None, dbt_kwargs=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/dbt/dbt.py#L97">[source]</a></span></div>
<p class="methods">If no profiles.yml file is found or if overwrite_profiles flag is set to True, this will first generate a profiles.yml file in the profiles_dir directory. Then run the dbt cli shell command.<br><br>**Args**:     <ul class="args"><li class="args">`command (string)`: shell command to be executed; can also be         provided at task initialization. Any variables / functions defined in         `self.helper_script` will be available in the same process this command         runs in     </li><li class="args">`env (dict, optional)`: dictionary of environment variables to use for         the subprocess     </li><li class="args">`helper_script (str, optional)`: a string representing a shell script, which         will be executed prior to the `command` in the same process. Can be used to         change directories, define helper functions, etc. when re-using this Task         for different commands in a Flow      </li><li class="args">`dbt_kwargs(dict, optional)`: keyword arguments used to populate the profiles.yml file</li></ul> **Returns**:     <ul class="args"><li class="args">`stdout (string)`: if `return_all` is `False` (the default), only the last line of         stdout is returned, otherwise all lines are returned, which is useful for         passing result of shell command to other downstream tasks. If there is no         output, `None` is returned.</li></ul> **Raises**:     <ul class="args"><li class="args">`prefect.engine.signals.FAIL`: if command has an exit code other         than 0</li></ul></p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on December 16, 2020 at 21:36 UTC</p>