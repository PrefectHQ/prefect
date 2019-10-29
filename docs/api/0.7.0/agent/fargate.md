---
sidebarDepth: 2
editLink: false
---
# Fargate Agent
---
 ## FargateAgent
 <div class='class-sig' id='prefect-agent-fargate-agent-fargateagent'><p class="prefect-sig">class </p><p class="prefect-class">prefect.agent.fargate.agent.FargateAgent</p>(name=None, labels=None, aws_access_key_id=None, aws_secret_access_key=None, aws_session_token=None, region_name=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/agent/fargate/agent.py#L11">[source]</a></span></div>

Agent which deploys flow runs as tasks using Fargate. This agent can run anywhere as long as the proper access configuration variables are set.  Information on using the Fargate Agent can be found at https://docs.prefect.io/cloud/agent/fargate.html

All `kwargs` are accepted that one would normally pass to boto3 for `register_task_definition` and `run_task`. For information on the kwargs supported visit the following links:

https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ecs.html#ECS.Client.register_task_definition

https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ecs.html#ECS.Client.run_task

**Args**:     <ul class="args"><li class="args">`name (str, optional)`: An optional name to give this agent. Can also be set through         the environment variable `PREFECT__CLOUD__AGENT__NAME`. Defaults to "agent"     </li><li class="args">`labels (List[str], optional)`: a list of labels, which are arbitrary string identifiers used by Prefect         Agents when polling for work     </li><li class="args">`aws_access_key_id (str, optional)`: AWS access key id for connecting the boto3         client. Defaults to the value set in the environment variable         `AWS_ACCESS_KEY_ID`.     </li><li class="args">`aws_secret_access_key (str, optional)`: AWS secret access key for connecting         the boto3 client. Defaults to the value set in the environment variable         `AWS_SECRET_ACCESS_KEY`.     </li><li class="args">`aws_session_token (str, optional)`: AWS session key for connecting the boto3         client. Defaults to the value set in the environment variable         `AWS_SESSION_TOKEN`.     </li><li class="args">`region_name (str, optional)`: AWS region name for connecting the boto3 client.         Defaults to the value set in the environment variable `REGION_NAME`.     </li><li class="args">`**kwargs (dict, optional)`: additional keyword arguments to pass to boto3 for         `register_task_definition` and `run_task`</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-agent-fargate-agent-fargateagent-deploy-flows'><p class="prefect-class">prefect.agent.fargate.agent.FargateAgent.deploy_flows</p>(flow_runs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/agent/fargate/agent.py#L143">[source]</a></span></div>
<p class="methods">Deploy flow runs to Fargate<br><br>**Args**:     <ul class="args"><li class="args">`flow_runs (list)`: A list of GraphQLResult flow run objects</li></ul></p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on October 29, 2019 at 19:43 UTC</p>