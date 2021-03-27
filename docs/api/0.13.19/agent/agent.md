---
sidebarDepth: 2
editLink: false
---
# Agent
---
 ## Agent
 <div class='class-sig' id='prefect-agent-agent-agent'><p class="prefect-sig">class </p><p class="prefect-class">prefect.agent.agent.Agent</p>(agent_config_id=None, name=None, labels=None, env_vars=None, max_polls=None, agent_address=None, no_cloud_logs=False)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/agent/agent.py#L79">[source]</a></span></div>

Base class for Agents. Information on using the Prefect agents can be found at https://docs.prefect.io/orchestration/agents/overview.html

This Agent class is a standard point for executing Flows in Prefect Cloud. It is meant to have subclasses which inherit functionality from this class. The only piece that the subclasses should implement is the `deploy_flows` function, which specifies how to run a Flow on the given platform. It is built in this way to keep Prefect Cloud logic standard but allows for platform specific customizability.

In order for this to operate `PREFECT__CLOUD__AGENT__AUTH_TOKEN` must be set as an environment variable or in your user configuration file.

**Args**:     <ul class="args"><li class="args">`agent_config_id (str, optional)`: An optional agent configuration ID that can be used to set         configuration based on an agent from a backend API. If set, all configuration values will be         pulled from backend agent configuration. If not set, any manual kwargs will be used.     </li><li class="args">`name (str, optional)`: An optional name to give this agent. Can also be set through         the environment variable `PREFECT__CLOUD__AGENT__NAME`. Defaults to "agent"     </li><li class="args">`labels (List[str], optional)`: a list of labels, which are arbitrary string         identifiers used by Prefect Agents when polling for work     </li><li class="args">`env_vars (dict, optional)`: a dictionary of environment variables and values that will         be set on each flow run that this agent submits for execution     </li><li class="args">`max_polls (int, optional)`: maximum number of times the agent will poll Prefect Cloud         for flow runs; defaults to infinite     </li><li class="args">`agent_address (str, optional)`: Address to serve internal api at. Currently this is         just health checks for use by an orchestration layer. Leave blank for no api server         (default).     </li><li class="args">`no_cloud_logs (bool, optional)`: Disable logging to a Prefect backend for this agent         and all deployed flow runs</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-agent-agent-agent-start'><p class="prefect-class">prefect.agent.agent.Agent.start</p>(_loop_intervals=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/agent/agent.py#L212">[source]</a></span></div>
<p class="methods">The main entrypoint to the agent. This function loops and constantly polls for new flow runs to deploy<br><br>**Args**:     <ul class="args"><li class="args">`_loop_intervals (dict, optional)`: Exposed for testing only.</li></ul></p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on December 16, 2020 at 21:36 UTC</p>