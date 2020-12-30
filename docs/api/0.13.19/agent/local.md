---
sidebarDepth: 2
editLink: false
---
# Local Agent
---
 ## LocalAgent
 <div class='class-sig' id='prefect-agent-local-agent-localagent'><p class="prefect-sig">class </p><p class="prefect-class">prefect.agent.local.agent.LocalAgent</p>(agent_config_id=None, name=None, labels=None, env_vars=None, import_paths=None, show_flow_logs=False, hostname_label=True, max_polls=None, agent_address=None, no_cloud_logs=False, storage_labels=True)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/agent/local/agent.py#L16">[source]</a></span></div>

Agent which deploys flow runs locally as subprocesses. There are a range of kwarg options to control information which may be provided to these subprocesses.

Optional import paths may be specified to append dependency modules to the PATH: 
```
prefect agent local start --import-path "/usr/local/my_module" --import-path "~/other_module"

# Now the local scripts/packages my_module and other_module will be importable in
# the flow's subprocess

```

Environment variables may be set on the agent to be provided to each flow run's subprocess: 
```
prefect agent local start --env MY_SECRET_KEY=secret --env OTHER_VAR=$OTHER_VAR

```

**Args**:     <ul class="args"><li class="args">`agent_config_id (str, optional)`: An optional agent configuration ID that can be used to set         configuration based on an agent from a backend API. If set all configuration values will be         pulled from backend agent configuration.     </li><li class="args">`name (str, optional)`: An optional name to give this agent. Can also be set through         the environment variable `PREFECT__CLOUD__AGENT__NAME`. Defaults to "agent"     </li><li class="args">`labels (List[str], optional)`: a list of labels, which are arbitrary string         identifiers used by Prefect Agents when polling for work     </li><li class="args">`env_vars (dict, optional)`: a dictionary of environment variables and values that will         be set on each flow run that this agent submits for execution     </li><li class="args">`max_polls (int, optional)`: maximum number of times the agent will poll Prefect Cloud         for flow runs; defaults to infinite     </li><li class="args">`agent_address (str, optional)`:  Address to serve internal api at. Currently this is         just health checks for use by an orchestration layer. Leave blank for no api server         (default).     </li><li class="args">`no_cloud_logs (bool, optional)`: Disable logging to a Prefect backend for this agent         and all deployed flow runs     </li><li class="args">`import_paths (List[str], optional)`: system paths which will be provided to each         Flow's runtime environment; useful for Flows which import from locally hosted         scripts or packages     </li><li class="args">`show_flow_logs (bool, optional)`: a boolean specifying whether the agent should         re-route Flow run logs to stdout; defaults to `False`     </li><li class="args">`hostname_label (boolean, optional)`: a boolean specifying whether this agent should         auto-label itself with the hostname of the machine it is running on.  Useful for         flows which are stored on the local filesystem.     </li><li class="args">`storage_labels (boolean, optional)`: a boolean specifying whether this agent should         auto-label itself with all of the storage options labels.</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-agent-agent-agent-start'><p class="prefect-class">prefect.agent.agent.Agent.start</p>(_loop_intervals=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/agent/agent.py#L212">[source]</a></span></div>
<p class="methods">The main entrypoint to the agent. This function loops and constantly polls for new flow runs to deploy<br><br>**Args**:     <ul class="args"><li class="args">`_loop_intervals (dict, optional)`: Exposed for testing only.</li></ul></p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on December 16, 2020 at 21:36 UTC</p>