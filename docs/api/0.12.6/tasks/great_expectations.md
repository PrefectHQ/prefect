---
sidebarDepth: 2
editLink: false
---
# Great Expectations Task
---
A collection of tasks for interacting with Great Expectations deployments and APIs.

Note that all tasks currently require being executed in an environment where the great expectations configuration directory can be found; 
learn more about how to initialize a great expectation deployment [on their Getting Started docs](https://docs.greatexpectations.io/en/latest/tutorials/getting_started.html).
 ## RunGreatExpectationsCheckpoint
 <div class='class-sig' id='prefect-tasks-great-expectations-checkpoints-rungreatexpectationscheckpoint'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.great_expectations.checkpoints.RunGreatExpectationsCheckpoint</p>(checkpoint_name=None, context_root_dir=None, runtime_environment=None, run_name=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/great_expectations/checkpoints.py#L22">[source]</a></span></div>

Task for running a Great Expectations checkpoint. For this task to run properly, it must be run above your great_expectations directory or configured with the `context_root_dir` for your great_expectations directory on the local file system of the worker process.

**Args**:     <ul class="args"><li class="args">`checkpoint_name (str)`: the name of the checkpoint; should match the filename of the         checkpoint without .py     </li><li class="args">`context_root_dir (str)`: the absolute or relative path to the directory holding your         `great_expectations.yml`     </li><li class="args">`runtime_environment (dict)`: a dictionary of great expectation config key-value pairs         to overwrite your config in `great_expectations.yml`     </li><li class="args">`run_name (str)`: the name of this Great Expectation validation run; defaults to the         task slug     </li><li class="args">`**kwargs (dict, optional)`: additional keyword arguments to pass to the Task constructor</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-great-expectations-checkpoints-rungreatexpectationscheckpoint-run'><p class="prefect-class">prefect.tasks.great_expectations.checkpoints.RunGreatExpectationsCheckpoint.run</p>(checkpoint_name=None, context_root_dir=None, runtime_environment=None, run_name=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/great_expectations/checkpoints.py#L55">[source]</a></span></div>
<p class="methods">Task run method.<br><br>**Args**:     <ul class="args"><li class="args">`checkpoint_name (str)`: the name of the checkpoint; should match the filename of         the checkpoint without .py     </li><li class="args">`context_root_dir (str)`: the absolute or relative path to the directory holding         your `great_expectations.yml`     </li><li class="args">`runtime_environment (dict)`: a dictionary of great expectation config key-value         pairs to overwrite your config in `great_expectations.yml`     </li><li class="args">`run_name (str)`: the name of this  Great Expectation validation run; defaults to         the task slug     </li><li class="args">`**kwargs (dict, optional)`: additional keyword arguments to pass to the Task         constructor</li></ul>**Raises**:     <ul class="args"></ul></p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on August 6, 2020 at 13:56 UTC</p>