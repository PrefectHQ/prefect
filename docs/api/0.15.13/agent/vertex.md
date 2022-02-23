---
sidebarDepth: 2
editLink: false
---
# Vertex Agent
---
 ## VertexAgent
 <div class='class-sig' id='prefect-agent-vertex-agent-vertexagent'><p class="prefect-sig">class </p><p class="prefect-class">prefect.agent.vertex.agent.VertexAgent</p>(project=None, region_name=None, service_account=None, agent_config_id=None, name=None, labels=None, env_vars=None, max_polls=None, agent_address=None, no_cloud_logs=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/agent/vertex/agent.py#L18">[source]</a></span></div>

Agent which deploys flow runs as Vertex Training tasks.

**Args**:     <ul class="args"><li class="args">`project (str)`: The project in which to submit the Vertex Jobs         This does not necessarily need to be the same project as the where         this agent is running, but the service account running the agent         needs permissions to start Vertex Job in this project.     </li><li class="args">`region_name (str, optional)`: Region the job is running in for the endpoint     </li><li class="args">`service_account (str, optional)`: Service account to submit jobs as on Vertex     </li><li class="args">`agent_config_id (str, optional)`: An optional agent configuration ID         that can be used to set configuration based on an agent from a         backend API. If set all configuration values will be pulled from         the backend agent configuration.     </li><li class="args">`name (str, optional)`: An optional name to give this agent. Can also         be set through the environment variable `PREFECT__CLOUD__AGENT__NAME`.         Defaults to "agent".     </li><li class="args">`labels (List[str], optional)`: A list of labels, which are arbitrary         string identifiers used by Prefect Agents when polling for work.     </li><li class="args">`env_vars (dict, optional)`: A dictionary of environment variables and         values that will be set on each flow run that this agent submits         for execution.     </li><li class="args">`max_polls (int, optional)`: Maximum number of times the agent will         poll Prefect Cloud for flow runs; defaults to infinite.     </li><li class="args">`agent_address (str, optional)`:  Address to serve internal api at.         Currently this is just health checks for use by an orchestration         layer. Leave blank for no api server (default).     </li><li class="args">`no_cloud_logs (bool, optional)`: Disable logging to a Prefect backend         for this agent and all deployed flow runs. Defaults to `False`.</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-agent-agent-agent-start'><p class="prefect-class">prefect.agent.agent.Agent.start</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/agent/agent.py#L180">[source]</a></span></div>
<p class="methods">The main entrypoint to the agent process. Sets up the agent then continuously polls for work to submit.<br><br>This is the only method that should need to be called externally.</p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on February 23, 2022 at 19:26 UTC</p>