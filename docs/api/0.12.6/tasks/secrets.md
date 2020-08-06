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
 ## SecretBase
 <div class='class-sig' id='prefect-tasks-secrets-base-secretbase'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.secrets.base.SecretBase</p>(**kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/secrets/base.py#L9">[source]</a></span></div>

Base Secrets Task.  This task does not perform any action but rather serves as the base task class which should be inherited from when writing new Secret Tasks.

Users should subclass this Task and override its `run` method for plugging into other Secret stores, as it is handled differently during execution to ensure the underlying secret value is not accidentally persisted in a non-safe location.

**Args**:     <ul class="args"><li class="args">`**kwargs (Any, optional)`: additional keyword arguments to pass to the Task constructor</li></ul>**Raises**:     <ul class="args"><li class="args">`ValueError`: if a `result` keyword is passed</li></ul>


---
<br>

 ## PrefectSecret
 <div class='class-sig' id='prefect-tasks-secrets-base-prefectsecret'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.secrets.base.PrefectSecret</p>(name, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/secrets/base.py#L33">[source]</a></span></div>

Prefect Secrets Task.  This task retrieves the underlying secret through the Prefect Secrets API (which has the ability to toggle between local vs. Cloud secrets).

**Args**:     <ul class="args"><li class="args">`name (str)`: The name of the underlying secret     </li><li class="args">`**kwargs (Any, optional)`: additional keyword arguments to pass to the Task constructor</li></ul>**Raises**:     <ul class="args"><li class="args">`ValueError`: if a `result` keyword is passed</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-secrets-base-prefectsecret-run'><p class="prefect-class">prefect.tasks.secrets.base.PrefectSecret.run</p>(name=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/secrets/base.py#L50">[source]</a></span></div>
<p class="methods">The run method for Secret Tasks.  This method actually retrieves and returns the underlying secret value using the `Secret.get()` method.  Note that this method first checks context for the secret value, and if not found either raises an error or queries Prefect Cloud, depending on whether `config.cloud.use_local_secrets` is `True` or `False`.<br><br>**Args**:     <ul class="args"><li class="args">`name (str, optional)`: the name of the underlying Secret to retrieve. Defaults         to the name provided at initialization.</li></ul>**Returns**:     <ul class="args"><li class="args">`Any`: the underlying value of the Prefect Secret</li></ul></p>|

---
<br>

 ## EnvVarSecret
 <div class='class-sig' id='prefect-tasks-secrets-env-var-envvarsecret'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.secrets.env_var.EnvVarSecret</p>(name, cast=None, raise_if_missing=False, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/secrets/env_var.py#L8">[source]</a></span></div>

A `Secret` task that retrieves a value from an environment variable.

**Args**:     <ul class="args"><li class="args">`name (str)`: the environment variable that contains the secret value     </li><li class="args">`cast (Callable[[Any], Any])`: A function that will be called on the Parameter         value to coerce it to a type.     </li><li class="args">`raise_if_missing (bool)`: if True, an error will be raised if the env var is not found.     </li><li class="args">`**kwargs (Any, optional)`: additional keyword arguments to pass to the Task constructor</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-secrets-env-var-envvarsecret-run'><p class="prefect-class">prefect.tasks.secrets.env_var.EnvVarSecret.run</p>(name=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/secrets/env_var.py#L31">[source]</a></span></div>
<p class="methods">Returns the value of an environment variable after applying an optional `cast` function.<br><br>**Args**:     <ul class="args"><li class="args">`name (str, optional)`: the name of the underlying environment variable to         retrieve. Defaults to the name provided at initialization.</li></ul>**Returns**:     <ul class="args"><li class="args">`Any`: the (optionally type-cast) value of the environment variable</li></ul>**Raises**:     <ul class="args"><li class="args">`ValueError`: if `raise_is_missing` is `True` and the environment variable was not found</li></ul></p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on August 6, 2020 at 13:56 UTC</p>