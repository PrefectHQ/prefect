---
sidebarDepth: 2
editLink: false
---
# Agent
---
 ## Agent
 <div class='class-sig' id='prefect-agent-agent-agent'><p class="prefect-sig">class </p><p class="prefect-class">prefect.agent.agent.Agent</p>(name=None, labels=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/agent/agent.py#L47">[source]</a></span></div>

Base class for Agents. Information on using the Prefect agents can be found at https://docs.prefect.io/cloud/agent/overview.html

This Agent class is a standard point for executing Flows in Prefect Cloud. It is meant to have subclasses which inherit functionality from this class. The only piece that the subclasses should implement is the `deploy_flows` function, which specifies how to run a Flow on the given platform. It is built in this way to keep Prefect Cloud logic standard but allows for platform specific customizability.

In order for this to operate `PREFECT__CLOUD__AGENT__AUTH_TOKEN` must be set as an environment variable or in your user configuration file.

**Args**:     <ul class="args"><li class="args">`name (str, optional)`: An optional name to give this agent. Can also be set through         the environment variable `PREFECT__CLOUD__AGENT__NAME`. Defaults to "agent"     </li><li class="args">`labels (List[str], optional)`: a list of labels, which are arbitrary string identifiers used by Prefect         Agents when polling for work</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-agent-agent-agent-agent-connect'><p class="prefect-class">prefect.agent.agent.Agent.agent_connect</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/agent/agent.py#L138">[source]</a></span></div>
<p class="methods">Verify agent connection to Prefect Cloud by finding and returning a tenant id<br><br>**Returns**:     <ul class="args"><li class="args">`str`: The current tenant id</li></ul></p>|
 | <div class='method-sig' id='prefect-agent-agent-agent-agent-process'><p class="prefect-class">prefect.agent.agent.Agent.agent_process</p>(tenant_id)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/agent/agent.py#L167">[source]</a></span></div>
<p class="methods">Full process for finding flow runs, updating states, and deploying.<br><br>**Args**:     <ul class="args"><li class="args">`tenant_id (str)`: The tenant id to use in the query</li></ul>**Returns**:     <ul class="args"><li class="args">`bool`: whether or not flow runs were found</li></ul></p>|
 | <div class='method-sig' id='prefect-agent-agent-agent-deploy-flow'><p class="prefect-class">prefect.agent.agent.Agent.deploy_flow</p>(flow_run)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/agent/agent.py#L400">[source]</a></span></div>
<p class="methods">Meant to be overridden by a platform specific deployment option<br><br>**Args**:     <ul class="args"><li class="args">`flow_run (GraphQLResult)`: A GraphQLResult flow run object</li></ul>**Returns**:     <ul class="args"><li class="args">`str`: Information about the deployment</li></ul>**Raises**:     <ul class="args"><li class="args">`ValueError`: if deployment attempted on unsupported Storage type</li></ul></p>|
 | <div class='method-sig' id='prefect-agent-agent-agent-heartbeat'><p class="prefect-class">prefect.agent.agent.Agent.heartbeat</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/agent/agent.py#L415">[source]</a></span></div>
<p class="methods">Meant to be overridden by a platform specific heartbeat option</p>|
 | <div class='method-sig' id='prefect-agent-agent-agent-mark-failed'><p class="prefect-class">prefect.agent.agent.Agent.mark_failed</p>(flow_run, exc)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/agent/agent.py#L357">[source]</a></span></div>
<p class="methods">Mark a flow run as `Failed`<br><br>**Args**:     <ul class="args"><li class="args">`flow_run (GraphQLResult)`: A GraphQLResult flow run object     </li><li class="args">`exc (Exception)`: An exception that was raised to use as the `Failed`         message</li></ul></p>|
 | <div class='method-sig' id='prefect-agent-agent-agent-query-flow-runs'><p class="prefect-class">prefect.agent.agent.Agent.query_flow_runs</p>(tenant_id)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/agent/agent.py#L222">[source]</a></span></div>
<p class="methods">Query Prefect Cloud for flow runs which need to be deployed and executed<br><br>**Args**:     <ul class="args"><li class="args">`tenant_id (str)`: The tenant id to use in the query</li></ul>**Returns**:     <ul class="args"><li class="args">`list`: A list of GraphQLResult flow run objects</li></ul></p>|
 | <div class='method-sig' id='prefect-agent-agent-agent-query-tenant-id'><p class="prefect-class">prefect.agent.agent.Agent.query_tenant_id</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/agent/agent.py#L207">[source]</a></span></div>
<p class="methods">Query Prefect Cloud for the tenant id that corresponds to the agent's auth token<br><br>**Returns**:     <ul class="args"><li class="args">`Union[str, None]`: The current tenant id if found, None otherwise</li></ul></p>|
 | <div class='method-sig' id='prefect-agent-agent-agent-start'><p class="prefect-class">prefect.agent.agent.Agent.start</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/agent/agent.py#L109">[source]</a></span></div>
<p class="methods">The main entrypoint to the agent. This function loops and constantly polls for new flow runs to deploy</p>|
 | <div class='method-sig' id='prefect-agent-agent-agent-update-state'><p class="prefect-class">prefect.agent.agent.Agent.update_state</p>(flow_run, deployment_info)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/agent/agent.py#L308">[source]</a></span></div>
<p class="methods">After a flow run is grabbed this function sets the state to Submitted so it won't be picked up by any other processes<br><br>**Args**:     <ul class="args"><li class="args">`flow_run (GraphQLResult)`: A GraphQLResult flow run object     </li><li class="args">`deployment_info (str)`: Identifier information related to the Flow Run         deployment</li></ul></p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on December 17, 2019 at 21:20 UTC</p>