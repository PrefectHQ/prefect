---
sidebarDepth: 2
editLink: false
---
# Local Agent
---
 ## LocalAgent
 <div class='class-sig' id='prefect-agent-local-agent-localagent'><p class="prefect-sig">class </p><p class="prefect-class">prefect.agent.local.agent.LocalAgent</p>(name=None, labels=None, env_vars=None, import_paths=None, show_flow_logs=False, hostname_label=True, max_polls=None, agent_address=None, no_cloud_logs=False)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/agent/local/agent.py#L14">[source]</a></span></div>

Agent which deploys flow runs locally as subprocesses. There are a range of kwarg options to control information which may be provided to these subprocesses.

Optional import paths may be specified to append dependency modules to the PATH: 
```
prefect agent start local --import-path "/usr/local/my_module" --import-path "~/other_module"

# Now the local scripts/packages my_module and other_module will be importable in
# the flow's subprocess

```

Environment variables may be set on the agent to be provided to each flow run's subprocess: 
```
prefect agent start local --env MY_SECRET_KEY=secret --env OTHER_VAR=$OTHER_VAR

```

**Args**:     <ul class="args"><li class="args">`name (str, optional)`: An optional name to give this agent. Can also be set through         the environment variable `PREFECT__CLOUD__AGENT__NAME`. Defaults to "agent"     </li><li class="args">`labels (List[str], optional)`: a list of labels, which are arbitrary string         identifiers used by Prefect Agents when polling for work     </li><li class="args">`env_vars (dict, optional)`: a dictionary of environment variables and values that will         be set on each flow run that this agent submits for execution     </li><li class="args">`max_polls (int, optional)`: maximum number of times the agent will poll Prefect Cloud         for flow runs; defaults to infinite     </li><li class="args">`agent_address (str, optional)`:  Address to serve internal api at. Currently this is         just health checks for use by an orchestration layer. Leave blank for no api server         (default).     </li><li class="args">`no_cloud_logs (bool, optional)`: Disable logging to a Prefect backend for this agent         and all deployed flow runs     </li><li class="args">`import_paths (List[str], optional)`: system paths which will be provided to each         Flow's runtime environment; useful for Flows which import from locally hosted         scripts or packages     </li><li class="args">`show_flow_logs (bool, optional)`: a boolean specifying whether the agent should         re-route Flow run logs to stdout; defaults to `False`     </li><li class="args">`hostname_label (boolean, optional)`: a boolean specifying whether this agent should         auto-label itself with the hostname of the machine it is running on.  Useful for         flows which are stored on the local filesystem.</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-agent-local-agent-localagent-deploy-flow'><p class="prefect-class">prefect.agent.local.agent.LocalAgent.deploy_flow</p>(flow_run)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/agent/local/agent.py#L112">[source]</a></span></div>
<p class="methods">Deploy flow runs on your local machine as Docker containers<br><br>**Args**:     <ul class="args"><li class="args">`flow_run (GraphQLResult)`: A GraphQLResult flow run object</li></ul>**Returns**:     <ul class="args"><li class="args">`str`: Information about the deployment</li></ul>**Raises**:     <ul class="args"><li class="args">`ValueError`: if deployment attempted on unsupported Storage type</li></ul></p>|
 | <div class='method-sig' id='prefect-agent-local-agent-localagent-generate-supervisor-conf'><p class="prefect-class">prefect.agent.local.agent.LocalAgent.generate_supervisor_conf</p>(token=None, labels=None, import_paths=None, show_flow_logs=False)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/agent/local/agent.py#L198">[source]</a></span></div>
<p class="methods">Generate and output an installable supervisorctl configuration file for the agent.<br><br>**Args**:     <ul class="args"><li class="args">`token (str, optional)`: A `RUNNER` token to give the agent     </li><li class="args">`labels (List[str], optional)`: a list of labels, which are arbitrary string         identifiers used by Prefect Agents when polling for work     </li><li class="args">`import_paths (List[str], optional)`: system paths which will be provided to each         Flow's runtime environment; useful for Flows which import from locally hosted         scripts or packages     </li><li class="args">`show_flow_logs (bool, optional)`: a boolean specifying whether the agent should         re-route Flow run logs to stdout; defaults to `False`</li></ul>**Returns**:     <ul class="args"><li class="args">`str`: A string representation of the generated configuration file</li></ul></p>|
 | <div class='method-sig' id='prefect-agent-local-agent-localagent-heartbeat'><p class="prefect-class">prefect.agent.local.agent.LocalAgent.heartbeat</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/agent/local/agent.py#L102">[source]</a></span></div>
<p class="methods">Meant to be overridden by a platform specific heartbeat option</p>|
 | <div class='method-sig' id='prefect-agent-local-agent-localagent-populate-env-vars'><p class="prefect-class">prefect.agent.local.agent.LocalAgent.populate_env_vars</p>(flow_run)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/agent/local/agent.py#L173">[source]</a></span></div>
<p class="methods">Populate metadata and variables in the environment variables for a flow run<br><br>**Args**:     <ul class="args"><li class="args">`flow_run (GraphQLResult)`: A flow run object</li></ul>**Returns**:     <ul class="args"><li class="args">`dict`: a dictionary representing the populated environment variables</li></ul></p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on August 6, 2020 at 13:56 UTC</p>