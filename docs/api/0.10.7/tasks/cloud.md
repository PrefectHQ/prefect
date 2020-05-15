---
sidebarDepth: 2
editLink: false
---
# Cloud Tasks
---
These tasks are classified as Cloud due to their reliance on Prefect Cloud.
 ## FlowRunTask
 <div class='class-sig' id='prefect-tasks-cloud-flow-run-flowruntask'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.cloud.flow_run.FlowRunTask</p>(flow_name=None, project_name=None, parameters=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/cloud/flow_run.py#L10">[source]</a></span></div>

Task used to kick off a flow run using Prefect Core's server or Prefect Cloud. If multiple versions of the flow are found, this task will kick off the most recent unarchived version.

**Args**:     <ul class="args"><li class="args">`flow_name (str, optional)`: the name of the flow to schedule; this value may also be provided at run time     </li><li class="args">`project_name (str, optional)`: the Cloud project in which the flow is located; this value may also be provided         at run time     </li><li class="args">`parameters (dict, optional)`: the parameters to pass to the flow run being scheduled; this value may also         be provided at run time     </li><li class="args">`**kwargs (dict, optional)`: additional keyword arguments to pass to the Task constructor</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-cloud-flow-run-flowruntask-run'><p class="prefect-class">prefect.tasks.cloud.flow_run.FlowRunTask.run</p>(flow_name=None, project_name=None, parameters=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/cloud/flow_run.py#L36">[source]</a></span></div>
<p class="methods">Run method for the task; responsible for scheduling the specified flow run.<br><br>**Args**:     <ul class="args"><li class="args">`flow_name (str, optional)`: the name of the flow to schedule; if not provided, this method will         use the flow name provided at initialization     </li><li class="args">`project_name (str, optional)`: the Cloud project in which the flow is located; if not provided, this method         will use the project provided at initialization     </li><li class="args">`parameters (dict, optional)`: the parameters to pass to the flow run being scheduled; if not provided,         this method will use the parameters provided at initialization</li></ul>**Returns**:     <ul class="args"><li class="args">`str`: the ID of the newly-scheduled flow run</li></ul>**Raises**:     <ul class="args"><li class="args">`ValueError`: if flow or project names were not provided, or if the flow provided cannot be found</li></ul>**Example**:     <br><pre class="language-python"><code class="language-python">    <span class="token keyword">from</span> prefect.tasks.cloud.flow_run <span class="token keyword">import</span> FlowRunTask<br><br>    kickoff_task <span class="token operator">=</span> FlowRunTask<span class="token punctuation">(</span>project_name<span class="token operator">=</span><span class="token string">"</span><span class="token string">My Cloud Project</span><span class="token string">"</span><span class="token punctuation">,</span> flow_name<span class="token operator">=</span><span class="token string">"</span><span class="token string">My Cloud Flow</span><span class="token string">"</span><span class="token punctuation">)</span><br>    <br></code></pre><br></p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on May 14, 2020 at 21:12 UTC</p>