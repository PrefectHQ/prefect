---
sidebarDepth: 2
editLink: false
---
# Kubernetes Agent
---
 ## KubernetesAgent
 <div class='class-sig' id='prefect-agent-kubernetes-agent-kubernetesagent'><p class="prefect-sig">class </p><p class="prefect-class">prefect.agent.kubernetes.agent.KubernetesAgent</p>(namespace=None, name=None, labels=None, env_vars=None, max_polls=None, agent_address=None, no_cloud_logs=False)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/agent/kubernetes/agent.py#L18">[source]</a></span></div>

Agent which deploys flow runs as Kubernetes jobs. Currently this is required to either run on a k8s cluster or on a local machine where the kube_config is pointing at the desired cluster. Information on using the Kubernetes Agent can be found at https://docs.prefect.io/orchestration/agents/kubernetes.html

Environment variables may be set on the agent to be provided to each flow run's job: 
```
prefect agent start kubernetes --env MY_SECRET_KEY=secret --env OTHER_VAR=$OTHER_VAR

```

Specifying a namespace for the agent will create flow run jobs in that namespace: 
```
prefect agent start kubernetes --namespace dev

```

**Args**:     <ul class="args"><li class="args">`namespace (str, optional)`: A Kubernetes namespace to create jobs in. Defaults         to the environment variable `NAMESPACE` or `default`.     </li><li class="args">`name (str, optional)`: An optional name to give this agent. Can also be set through         the environment variable `PREFECT__CLOUD__AGENT__NAME`. Defaults to "agent"     </li><li class="args">`labels (List[str], optional)`: a list of labels, which are arbitrary string identifiers used by Prefect         Agents when polling for work     </li><li class="args">`env_vars (dict, optional)`: a dictionary of environment variables and values that will be set         on each flow run that this agent submits for execution     </li><li class="args">`max_polls (int, optional)`: maximum number of times the agent will poll Prefect Cloud for flow runs;         defaults to infinite     </li><li class="args">`agent_address (str, optional)`:  Address to serve internal api at. Currently this is         just health checks for use by an orchestration layer. Leave blank for no api server (default).     </li><li class="args">`no_cloud_logs (bool, optional)`: Disable logging to a Prefect backend for this agent and all deployed flow runs</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-agent-kubernetes-agent-kubernetesagent-deploy-flow'><p class="prefect-class">prefect.agent.kubernetes.agent.KubernetesAgent.deploy_flow</p>(flow_run)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/agent/kubernetes/agent.py#L88">[source]</a></span></div>
<p class="methods">Deploy flow runs on to a k8s cluster as jobs<br><br>**Args**:     <ul class="args"><li class="args">`flow_run (GraphQLResult)`: A GraphQLResult flow run object</li></ul>**Returns**:     <ul class="args"><li class="args">`str`: Information about the deployment</li></ul>**Raises**:     <ul class="args"><li class="args">`ValueError`: if deployment attempted on unsupported Storage type</li></ul></p>|
 | <div class='method-sig' id='prefect-agent-kubernetes-agent-kubernetesagent-generate-deployment-yaml'><p class="prefect-class">prefect.agent.kubernetes.agent.KubernetesAgent.generate_deployment_yaml</p>(token=None, api=None, namespace=None, image_pull_secrets=None, resource_manager_enabled=False, rbac=False, latest=False, mem_request=None, mem_limit=None, cpu_request=None, cpu_limit=None, labels=None, env_vars=None, backend=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/agent/kubernetes/agent.py#L197">[source]</a></span></div>
<p class="methods">Generate and output an installable YAML spec for the agent.<br><br>**Args**:     <ul class="args"><li class="args">`token (str, optional)`: A `RUNNER` token to give the agent     </li><li class="args">`api (str, optional)`: A URL pointing to the Prefect API. Defaults to         `https://api.prefect.io`     </li><li class="args">`namespace (str, optional)`: The namespace to create Prefect jobs in. Defaults         to `default`     </li><li class="args">`image_pull_secrets (str, optional)`: The name of an image pull secret to use         for Prefect jobs     </li><li class="args">`resource_manager_enabled (bool, optional)`: Whether to include the resource         manager as part of the YAML. Defaults to `False`     </li><li class="args">`rbac (bool, optional)`: Whether to include default RBAC configuration as         part of the YAML. Defaults to `False`     </li><li class="args">`latest (bool, optional)`: Whether to use the `latest` Prefect image.         Defaults to `False`     </li><li class="args">`mem_request (str, optional)`: Requested memory for Prefect init job.     </li><li class="args">`mem_limit (str, optional)`: Limit memory for Prefect init job.     </li><li class="args">`cpu_request (str, optional)`: Requested CPU for Prefect init job.     </li><li class="args">`cpu_limit (str, optional)`: Limit CPU for Prefect init job.     </li><li class="args">`labels (List[str], optional)`: a list of labels, which are arbitrary string         identifiers used by Prefect Agents when polling for work     </li><li class="args">`env_vars (dict, optional)`: additional environment variables to attach to all         jobs created by this agent     </li><li class="args">`backend (str, optional)`: toggle which backend to use for this agent.         Defaults to backend currently set in config.</li></ul>**Returns**:     <ul class="args"><li class="args">`str`: A string representation of the generated YAML</li></ul></p>|
 | <div class='method-sig' id='prefect-agent-kubernetes-agent-kubernetesagent-replace-job-spec-yaml'><p class="prefect-class">prefect.agent.kubernetes.agent.KubernetesAgent.replace_job_spec_yaml</p>(flow_run)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/agent/kubernetes/agent.py#L125">[source]</a></span></div>
<p class="methods">Populate metadata and variables in the job_spec.yaml file for flow runs<br><br>**Args**:     <ul class="args"><li class="args">`flow_run (GraphQLResult)`: A flow run object</li></ul>**Returns**:     <ul class="args"><li class="args">`dict`: a dictionary representing the populated yaml object</li></ul></p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on May 14, 2020 at 21:12 UTC</p>