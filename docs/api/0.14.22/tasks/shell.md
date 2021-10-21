---
sidebarDepth: 2
editLink: false
---
# Shell Tasks
---
 ## ShellTask
 <div class='class-sig' id='prefect-tasks-shell-shelltask'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.shell.ShellTask</p>(command=None, env=None, helper_script=None, shell=&quot;bash&quot;, return_all=False, log_stderr=False, stream_output=False, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/shell.py#L12">[source]</a></span></div>

Task for running arbitrary shell commands.

NOTE: This task combines stderr and stdout because reading from both       streams without blocking is tricky.

**Args**:     <ul class="args"><li class="args">`command (string, optional)`: shell command to be executed; can also be         provided post-initialization by calling this task instance     </li><li class="args">`env (dict, optional)`: dictionary of environment variables to use for         the subprocess; can also be provided at runtime     </li><li class="args">`helper_script (str, optional)`: a string representing a shell script, which         will be executed prior to the `command` in the same process. Can be used to         change directories, define helper functions, etc. when re-using this Task         for different commands in a Flow; can also be provided at runtime     </li><li class="args">`shell (string, optional)`: shell to run the command with; defaults to "bash"     </li><li class="args">`return_all (bool, optional)`: boolean specifying whether this task         should return all lines of stdout as a list, or just the last line         as a string; defaults to `False`     </li><li class="args">`log_stderr (bool, optional)`: boolean specifying whether this task should log         the output in the case of a non-zero exit code; defaults to `False`. This          actually logs both stderr and stdout and will only log the last line of          output unless `return_all` is `True`     </li><li class="args">`stream_output (Union[bool, int, str], optional)`: specifies whether this task should log         the output as it occurs, and at what logging level. If `True` is passed,         the logging level defaults to `INFO`; otherwise, any integer or string         value that's passed will be treated as the log level, provided         the `logging` library can successfully interpret it. If enabled,         `log_stderr` will be ignored as the output will have already been         logged. defaults to `False`     </li><li class="args">`**kwargs`: additional keyword arguments to pass to the Task constructor</li></ul> **Raises**:     <ul class="args"><li class="args">`TypeError`: if `stream_output` is passed in as a string, but cannot       successfully be converted to a numeric value by logging.getLevelName()</li></ul> **Example**:     
```python
    from prefect import Flow
    from prefect.tasks.shell import ShellTask

    task = ShellTask(helper_script="cd ~")
    with Flow("My Flow") as f:
        # both tasks will be executed in home directory
        contents = task(command='ls')
        mv_file = task(command='mv .vimrc /.vimrc')

    out = f.run()

```

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-shell-shelltask-run'><p class="prefect-class">prefect.tasks.shell.ShellTask.run</p>(command=None, env=None, helper_script=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/shell.py#L92">[source]</a></span></div>
<p class="methods">Run the shell command.<br><br>**Args**:     <ul class="args"><li class="args">`command (string)`: shell command to be executed; can also be         provided at task initialization. Any variables / functions defined in         `helper_script` will be available in the same process this command         runs in     </li><li class="args">`env (dict, optional)`: dictionary of environment variables to use for         the subprocess     </li><li class="args">`helper_script (str, optional)`: a string representing a shell script, which         will be executed prior to the `command` in the same process. Can be used to         change directories, define helper functions, etc. when re-using this Task         for different commands in a Flow</li></ul> **Returns**:     <ul class="args"><li class="args">`output (string)`: if `return_all` is `False` (the default), only         the last line of output is returned, otherwise all lines are         returned, which is useful for passing result of shell command         to other downstream tasks. If there is no output, `None` is         returned.</li></ul> **Raises**:     <ul class="args"><li class="args">`prefect.engine.signals.FAIL`: if command has an exit code other         than 0</li></ul></p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on July 1, 2021 at 18:35 UTC</p>