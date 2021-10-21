---
sidebarDepth: 2
editLink: false
---
# Asana Tasks
---
 ## OpenAsanaToDo
 <div class='class-sig' id='prefect-tasks-asana-asana-task-openasanatodo'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.asana.asana_task.OpenAsanaToDo</p>(name=None, notes=None, project=None, token=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/asana/asana_task.py#L11">[source]</a></span></div>

Task for opening / creating new Asana tasks using the Asana REST API.

**Args**:     <ul class="args"><li class="args">`project (str; , required)`: The GID of the project the task will be posted to;         can also be provided to the `run` method     </li><li class="args">`name (str, optional)`: the name of the task to create; can also be provided to the         `run` method     </li><li class="args">`notes (str, optional)`: the contents of the task; can also be provided to the `run` method     </li><li class="args">`token (str)`: an Asana Personal Access Token     </li><li class="args">`**kwargs (Any, optional)`: additional keyword arguments to pass to the standard Task         init method</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-asana-asana-task-openasanatodo-run'><p class="prefect-class">prefect.tasks.asana.asana_task.OpenAsanaToDo.run</p>(name=None, notes=None, project=None, token=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/asana/asana_task.py#L40">[source]</a></span></div>
<p class="methods">Run method for this Task. Invoked by calling this Task after initialization within a Flow context, or by using `Task.bind`.<br><br>**Args**: <ul class="args"><li class="args">`name (str, optional)`: the name of the task to create; can also be provided at initialization </li><li class="args">`project (str; , required)`: The GID of the project the task will be posted to;     can also be provided at initialization </li><li class="args">`notes (str, optional)`: the contents of the task; can also be provided at initialization </li><li class="args">`token (str)`: an ASANA Personal Access Token</li></ul> **Raises**:     <ul class="args"><li class="args">`ValueError`: if no project is provided     </li><li class="args">`ValueError`: if no access token is provided     </li><li class="args">`ValueError`: if no result is returned</li></ul> **Returns**:     <ul class="args"><li class="args">The result object with details of the new asana task</li></ul></p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on July 1, 2021 at 18:35 UTC</p>