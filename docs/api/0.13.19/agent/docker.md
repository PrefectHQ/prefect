---
sidebarDepth: 2
editLink: false
---
# Docker Agent
---
 ## DockerAgent
 <div class='class-sig' id='prefect-agent-docker-agent-dockeragent'><p class="prefect-sig">class </p><p class="prefect-class">prefect.agent.docker.agent.DockerAgent</p>(agent_config_id=None, name=None, labels=None, env_vars=None, max_polls=None, agent_address=None, no_cloud_logs=False, base_url=None, no_pull=None, volumes=None, show_flow_logs=False, network=None, docker_interface=True, reg_allow_list=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/agent/docker/agent.py#L35">[source]</a></span></div>

Agent which deploys flow runs locally as Docker containers. Information on using the Docker Agent can be found at https://docs.prefect.io/orchestration/agents/docker.html

Environment variables may be set on the agent to be provided to each flow run's container: 
```
prefect agent docker start --env MY_SECRET_KEY=secret --env OTHER_VAR=$OTHER_VAR

```

The default Docker daemon may be overridden by providing a different `base_url`: 
```
prefect agent docker start --base-url "tcp://0.0.0.0:2375"

```

**Args**:     <ul class="args"><li class="args">`agent_config_id (str, optional)`: An optional agent configuration ID that can be used to set         configuration based on an agent from a backend API. If set all configuration values will be         pulled from backend agent configuration.     </li><li class="args">`name (str, optional)`: An optional name to give this agent. Can also be set through         the environment variable `PREFECT__CLOUD__AGENT__NAME`. Defaults to "agent"     </li><li class="args">`labels (List[str], optional)`: a list of labels, which are arbitrary string         identifiers used by Prefect Agents when polling for work     </li><li class="args">`env_vars (dict, optional)`: a dictionary of environment variables and values that will         be set on each flow run that this agent submits for execution     </li><li class="args">`max_polls (int, optional)`: maximum number of times the agent will poll Prefect Cloud         for flow runs; defaults to infinite     </li><li class="args">`agent_address (str, optional)`:  Address to serve internal api at. Currently this is         just health checks for use by an orchestration layer. Leave blank for no api server         (default).     </li><li class="args">`no_cloud_logs (bool, optional)`: Disable logging to a Prefect backend for this agent         and all deployed flow runs     </li><li class="args">`base_url (str, optional)`: URL for a Docker daemon server. Defaults to         `unix:///var/run/docker.sock` however other hosts such as         `tcp://0.0.0.0:2375` can be provided     </li><li class="args">`no_pull (bool, optional)`: Flag on whether or not to pull flow images.         Defaults to `False` if not provided here or in context.     </li><li class="args">`show_flow_logs (bool, optional)`: a boolean specifying whether the agent should         re-route Flow run logs to stdout; defaults to `False`     </li><li class="args">`volumes (List[str], optional)`: a list of Docker volume mounts to be attached to any         and all created containers.     </li><li class="args">`network (str, optional)`: Add containers to an existing docker network     </li><li class="args">`docker_interface (bool, optional)`: Toggle whether or not a `docker0` interface is         present on this machine.  Defaults to `True`. **Note**: This is mostly relevant for         some Docker-in-Docker setups that users may be running their agent with.     </li><li class="args">`reg_allow_list (List[str], optional)`: Limits Docker Agent to only pull images         from the listed registries.</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-agent-agent-agent-start'><p class="prefect-class">prefect.agent.agent.Agent.start</p>(_loop_intervals=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/agent/agent.py#L212">[source]</a></span></div>
<p class="methods">The main entrypoint to the agent. This function loops and constantly polls for new flow runs to deploy<br><br>**Args**:     <ul class="args"><li class="args">`_loop_intervals (dict, optional)`: Exposed for testing only.</li></ul></p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on December 16, 2020 at 21:36 UTC</p>