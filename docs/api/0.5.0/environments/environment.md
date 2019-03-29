---
sidebarDepth: 2
editLink: false
---
# Environments
---
 ## Environment
 <div class='class-sig' id='prefect-environments-environment-environment'><p class="prefect-sig">class </p><p class="prefect-class">prefect.environments.environment.Environment</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/environment.py#L35">[source]</a></span></div>

Base class for Environments.

An environment is an object that can be instantiated in a way that makes it possible to call `environment.run()` and run a flow.

Because certain `__init__` parameters may not be known when the Environment is first created, including which Flow to run, Environments have a `build()` method that takes a `Flow` argument and returns an Environment with all `__init__` parameters specified.

The setup and execute functions are limited to environments which have an infrastructure requirement. However the build and run functions are limited to base environments such as (LocalEnvironment and DockerEnvironment) from which infrastructure dependent environments inherit from.

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-environments-environment-environment-build'><p class="prefect-class">prefect.environments.environment.Environment.build</p>(flow)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/environment.py#L55">[source]</a></span></div>
<p class="methods">Builds the environment for a specific flow. A new environment is returned.<br><br>**Args**:     <ul class="args"><li class="args">`flow (prefect.Flow)`: the Flow for which the environment will be built</li></ul>**Returns**:     <ul class="args"><li class="args">`Environment`: a new environment that can run the provided Flow.</li></ul></p>|
 | <div class='method-sig' id='prefect-environments-environment-environment-execute'><p class="prefect-class">prefect.environments.environment.Environment.execute</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/environment.py#L67">[source]</a></span></div>
<p class="methods">Executes the environment on any infrastructure created during setup</p>|
 | <div class='method-sig' id='prefect-environments-environment-environment-run'><p class="prefect-class">prefect.environments.environment.Environment.run</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/environment.py#L73">[source]</a></span></div>
<p class="methods">Runs the `Flow` represented by this environment.<br><br>**Returns**:     <ul class="args"><li class="args">`prefect.engine.state.State`: the state of the flow run</li></ul></p>|
 | <div class='method-sig' id='prefect-environments-environment-environment-serialize'><p class="prefect-class">prefect.environments.environment.Environment.serialize</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/environment.py#L88">[source]</a></span></div>
<p class="methods">Returns a serialized version of the Environment<br><br>**Returns**:     <ul class="args"><li class="args">`dict`: the serialized Environment</li></ul></p>|
 | <div class='method-sig' id='prefect-environments-environment-environment-setup'><p class="prefect-class">prefect.environments.environment.Environment.setup</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/environment.py#L82">[source]</a></span></div>
<p class="methods">Sets up the infrastructure needed for this environment</p>|
 | <div class='method-sig' id='prefect-environments-environment-environment-to-file'><p class="prefect-class">prefect.environments.environment.Environment.to_file</p>(path)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/environment.py#L98">[source]</a></span></div>
<p class="methods">Serialize the environment to a file.<br><br>**Args**:     <ul class="args"><li class="args">`path (str)`: the file path to which the environment will be written</li></ul></p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>by Prefect 0.5.0 on March 29, 2019 at 17:39 UTC</p>
