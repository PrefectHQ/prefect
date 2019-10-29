---
sidebarDepth: 2
editLink: false
---
# Secret Tasks
---
Secret Tasks are a special kind of Prefect Task used to represent the retrieval of sensitive data.

The base implementation uses Prefect Cloud secrets, but users are encouraged to subclass the `Secret` task
class for interacting with other secret providers. Secrets always use a special kind of result handler that
prevents the persistence of sensitive information.
 ## Secret
 <div class='class-sig' id='prefect-tasks-secrets-base-secret'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.secrets.base.Secret</p>(name, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/secrets/base.py#L8">[source]</a></span></div>

Base Prefect Secrets Task.  This task retrieves the underlying secret through the Prefect Secrets API (which has the ability to toggle between local vs. Cloud secrets). Users should subclass this Task and override its `run` method for plugging into other Secret stores, as it is handled differently during execution to ensure the underlying secret value is not accidentally persisted in a non-safe location.

**Args**:     <ul class="args"><li class="args">`name (str)`: The name of the underlying secret     </li><li class="args">`**kwargs (Any, optional)`: additional keyword arguments to pass to the Task constructor</li></ul>**Raises**:     <ul class="args"><li class="args">`ValueError`: if a `result_handler` keyword is passed</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-secrets-base-secret-run'><p class="prefect-class">prefect.tasks.secrets.base.Secret.run</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/secrets/base.py#L33">[source]</a></span></div>
<p class="methods">The run method for Secret Tasks.  This method actually retrieves and returns the underlying secret value using the `Secret.get()` method.  Note that this method first checks context for the secret value, and if not found either raises an error or queries Prefect Cloud, depending on whether `config.cloud.use_local_secrets` is `True` or `False`.<br><br>**Returns**:     <ul class="args"><li class="args">`Any`: the underlying value of the Prefect Secret</li></ul></p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on October 29, 2019 at 19:43 UTC</p>