---
sidebarDepth: 2
editLink: false
---
# Docker Agent
---
 ## DockerAgent
 <div class='class-sig' id='prefect-agent-docker-agent-dockeragent'><p class="prefect-sig">class </p><p class="prefect-class">prefect.agent.docker.agent.DockerAgent</p>(name=None, labels=None, env_vars=None, base_url=None, no_pull=None, volumes=None, show_flow_logs=False)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/agent/docker/agent.py#L18">[source]</a></span></div>

Agent which deploys flow runs locally as Docker containers. Information on using the Docker Agent can be found at https://docs.prefect.io/cloud/agents/docker.html

Environment variables may be set on the agent to be provided to each flow run's container: 
```
prefect agent start docker --env MY_SECRET_KEY=secret --env OTHER_VAR=$OTHER_VAR

```

The default Docker daemon may be overridden by providing a different `base_url`: 
```
prefect agent start docker --base-url "tcp://0.0.0.0:2375"

```

**Args**:     <ul class="args"><li class="args">`name (str, optional)`: An optional name to give this agent. Can also be set through         the environment variable `PREFECT__CLOUD__AGENT__NAME`. Defaults to "agent"     </li><li class="args">`labels (List[str], optional)`: a list of labels, which are arbitrary string identifiers used by Prefect         Agents when polling for work     </li><li class="args">`env_vars (dict, optional)`: a dictionary of environment variables and values that will be set         on each flow run that this agent submits for execution     </li><li class="args">`base_url (str, optional)`: URL for a Docker daemon server. Defaults to         `unix:///var/run/docker.sock` however other hosts such as         `tcp://0.0.0.0:2375` can be provided     </li><li class="args">`no_pull (bool, optional)`: Flag on whether or not to pull flow images.         Defaults to `False` if not provided here or in context.     </li><li class="args">`show_flow_logs (bool, optional)`: a boolean specifying whether the agent should re-route Flow run logs         to stdout; defaults to `False`     </li><li class="args">`volumes (List[str], optional)`: a list of Docker volume mounts to be attached to any and all created containers.</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-agent-docker-agent-dockeragent-deploy-flow'><p class="prefect-class">prefect.agent.docker.agent.DockerAgent.deploy_flow</p>(flow_run)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/agent/docker/agent.py#L269">[source]</a></span></div>
<p class="methods">Deploy flow runs on your local machine as Docker containers<br><br>**Args**:     <ul class="args"><li class="args">`flow_run (GraphQLResult)`: A GraphQLResult flow run object</li></ul>**Returns**:     <ul class="args"><li class="args">`str`: Information about the deployment</li></ul>**Raises**:     <ul class="args"><li class="args">`ValueError`: if deployment attempted on unsupported Storage type</li></ul></p>|
 | <div class='method-sig' id='prefect-agent-docker-agent-dockeragent-heartbeat'><p class="prefect-class">prefect.agent.docker.agent.DockerAgent.heartbeat</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/agent/docker/agent.py#L106">[source]</a></span></div>
<p class="methods">Meant to be overridden by a platform specific heartbeat option</p>|
 | <div class='method-sig' id='prefect-agent-docker-agent-dockeragent-on-shutdown'><p class="prefect-class">prefect.agent.docker.agent.DockerAgent.on_shutdown</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/agent/docker/agent.py#L123">[source]</a></span></div>
<p class="methods">Cleanup any child processes created for streaming logs. This is to prevent logs from displaying on the terminal after the agent exits.</p>|
 | <div class='method-sig' id='prefect-agent-docker-agent-dockeragent-populate-env-vars'><p class="prefect-class">prefect.agent.docker.agent.DockerAgent.populate_env_vars</p>(flow_run)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/agent/docker/agent.py#L369">[source]</a></span></div>
<p class="methods">Populate metadata and variables in the environment variables for a flow run<br><br>**Args**:     <ul class="args"><li class="args">`flow_run (GraphQLResult)`: A flow run object</li></ul>**Returns**:     <ul class="args"><li class="args">`dict`: a dictionary representing the populated environment variables</li></ul></p>|
 | <div class='method-sig' id='prefect-agent-docker-agent-dockeragent-stream-container-logs'><p class="prefect-class">prefect.agent.docker.agent.DockerAgent.stream_container_logs</p>(container_id)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/agent/docker/agent.py#L357">[source]</a></span></div>
<p class="methods">Stream container logs back to stdout<br><br>**Args**:     <ul class="args"><li class="args">`container_id (str)`: ID of a container to stream logs</li></ul></p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on March 30, 2020 at 17:55 UTC</p>