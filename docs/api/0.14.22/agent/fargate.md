---
sidebarDepth: 2
editLink: false
---
# Fargate Agent
---
 ## FargateAgent
 <div class='class-sig' id='prefect-agent-fargate-agent-fargateagent'><p class="prefect-sig">class </p><p class="prefect-class">prefect.agent.fargate.agent.FargateAgent</p>(agent_config_id=None, name=None, labels=None, env_vars=None, max_polls=None, agent_address=None, no_cloud_logs=None, launch_type=&quot;FARGATE&quot;, aws_access_key_id=None, aws_secret_access_key=None, aws_session_token=None, region_name=None, botocore_config=None, enable_task_revisions=False, use_external_kwargs=False, external_kwargs_s3_bucket=None, external_kwargs_s3_key=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/agent/fargate/agent.py#L17">[source]</a></span></div>

Agent which deploys flow runs as tasks using Fargate.

DEPRECATED: The Fargate agent is deprecated, please transition to using the ECS agent instead.

This agent can run anywhere as long as the proper access configuration variables are set.  Information on using the Fargate Agent can be found at https://docs.prefect.io/orchestration/agents/fargate.html

All `kwargs` are accepted that one would normally pass to boto3 for `register_task_definition` and `run_task`. For information on the kwargs supported visit the following links:

https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ecs.html#ECS.Client.register_task_definition

https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ecs.html#ECS.Client.run_task

**Note**: if AWS authentication kwargs such as `aws_access_key_id` and `aws_session_token` are not provided they will be read from the environment.

Environment variables may be set on the agent to be provided to each flow run's Fargate task: 
```
prefect agent fargate start --env MY_SECRET_KEY=secret --env OTHER_VAR=$OTHER_VAR

```

boto3 kwargs being provided to the Fargate Agent: 
```
prefect agent fargate start \
    networkConfiguration="{\
        'awsvpcConfiguration': {\
            'assignPublicIp': 'ENABLED',\
            'subnets': ['my_subnet_id'],\
            'securityGroups': []\
        }\
    }"

```

botocore configuration options can be provided to the Fargate Agent: 
```
FargateAgent(botocore_config={"retries": {"max_attempts": 10}})

```

**Args**:     <ul class="args"><li class="args">`agent_config_id (str, optional)`: An optional agent configuration ID that can be used to set         configuration based on an agent from a backend API. If set all configuration values will be         pulled from backend agent configuration.     </li><li class="args">`name (str, optional)`: An optional name to give this agent. Can also be set through         the environment variable `PREFECT__CLOUD__AGENT__NAME`. Defaults to "agent"     </li><li class="args">`labels (List[str], optional)`: a list of labels, which are arbitrary string         identifiers used by Prefect Agents when polling for work     </li><li class="args">`env_vars (dict, optional)`: a dictionary of environment variables and values that will         be set on each flow run that this agent submits for execution     </li><li class="args">`max_polls (int, optional)`: maximum number of times the agent will poll Prefect Cloud         for flow runs; defaults to infinite     </li><li class="args">`agent_address (str, optional)`:  Address to serve internal api at. Currently this is         just health checks for use by an orchestration layer. Leave blank for no api server         (default).     </li><li class="args">`no_cloud_logs (bool, optional)`: Disable logging to a Prefect backend for this agent         and all deployed flow runs     </li><li class="args">`launch_type (str, optional)`: either FARGATE or EC2, defaults to FARGATE     </li><li class="args">`aws_access_key_id (str, optional)`: AWS access key id for connecting the boto3         client. Defaults to the value set in the environment variable         `AWS_ACCESS_KEY_ID` or `None`     </li><li class="args">`aws_secret_access_key (str, optional)`: AWS secret access key for connecting         the boto3 client. Defaults to the value set in the environment variable         `AWS_SECRET_ACCESS_KEY` or `None`     </li><li class="args">`aws_session_token (str, optional)`: AWS session key for connecting the boto3         client. Defaults to the value set in the environment variable         `AWS_SESSION_TOKEN` or `None`     </li><li class="args">`region_name (str, optional)`: AWS region name for connecting the boto3 client.         Defaults to the value set in the environment variable `REGION_NAME` or `None`     </li><li class="args">`botocore_config (dict, optional)`: botocore configuration options to be passed to the         boto3 client.         https://botocore.amazonaws.com/v1/documentation/api/latest/reference/config.html     </li><li class="args">`enable_task_revisions (bool, optional)`: Enable registration of task definitions using         revisions.  When enabled, task definitions will use flow name as opposed to flow id         and each new version will be a task definition revision. Each revision will be         registered with a tag called 'PrefectFlowId' and 'PrefectFlowVersion' to enable         proper lookup for existing revisions.  Flow name is reformatted to support task         definition naming rules by converting all non-alphanumeric characters to '_'.         Defaults to False.     </li><li class="args">`use_external_kwargs (bool, optional)`: When enabled, the agent will check for the         existence of an external json file containing kwargs to pass into the run_flow         process.  Defaults to False.     </li><li class="args">`external_kwargs_s3_bucket (str, optional)`: S3 bucket containing external kwargs.     </li><li class="args">`external_kwargs_s3_key (str, optional)`: S3 key prefix for the location of         <slugified_flow_name>/<flow_id[:8]>.json.     </li><li class="args">`**kwargs (dict, optional)`: additional keyword arguments to pass to boto3 for         `register_task_definition` and `run_task`</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-agent-agent-agent-start'><p class="prefect-class">prefect.agent.agent.Agent.start</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/agent/agent.py#L173">[source]</a></span></div>
<p class="methods">The main entrypoint to the agent process. Sets up the agent then continuously polls for work to submit.<br><br>This is the only method that should need to be called externally.</p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on July 1, 2021 at 18:35 UTC</p>