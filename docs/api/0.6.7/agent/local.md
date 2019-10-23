---
sidebarDepth: 2
editLink: false
---
# Local Agent
---
 ## LocalAgent
 <div class='class-sig' id='prefect-agent-local-agent-localagent'><p class="prefect-sig">class </p><p class="prefect-class">prefect.agent.local.agent.LocalAgent</p>(name=None, base_url=None, no_pull=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/agent/local/agent.py#L12">[source]</a></span></div>

Agent which deploys flow runs locally as Docker containers. Information on using the Local Agent can be found at https://docs.prefect.io/cloud/agent/local.html

**Args**:     <ul class="args"><li class="args">`name (str, optional)`: An optional name to give this agent. Can also be set through         the environment variable `PREFECT__CLOUD__AGENT__NAME`. Defaults to "agent"     </li><li class="args">`base_url (str, optional)`: URL for a Docker daemon server. Defaults to         `unix:///var/run/docker.sock` however other hosts such as         `tcp://0.0.0.0:2375` can be provided     </li><li class="args">`no_pull (bool, optional)`: Flag on whether or not to pull flow images.         Defaults to `False` if not provided here or in context.</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-agent-local-agent-localagent-deploy-flows'><p class="prefect-class">prefect.agent.local.agent.LocalAgent.deploy_flows</p>(flow_runs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/agent/local/agent.py#L60">[source]</a></span></div>
<p class="methods">Deploy flow runs on your local machine as Docker containers<br><br>**Args**:     <ul class="args"><li class="args">`flow_runs (list)`: A list of GraphQLResult flow run objects</li></ul></p>|
 | <div class='method-sig' id='prefect-agent-local-agent-localagent-populate-env-vars'><p class="prefect-class">prefect.agent.local.agent.LocalAgent.populate_env_vars</p>(flow_run)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/agent/local/agent.py#L104">[source]</a></span></div>
<p class="methods">Populate metadata and variables in the environment variables for a flow run<br><br>**Args**:     <ul class="args"><li class="args">`flow_run (GraphQLResult)`: A flow run object</li></ul>**Returns**:     <ul class="args"><li class="args">`dict`: a dictionary representing the populated environment variables</li></ul></p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on October 17, 2019 at 13:42 UTC</p>