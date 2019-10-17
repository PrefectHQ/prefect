---
sidebarDepth: 2
editLink: false
---
# Kubernetes Agent
---
 ## KubernetesAgent
 <div class='class-sig' id='prefect-agent-kubernetes-agent-kubernetesagent'><p class="prefect-sig">class </p><p class="prefect-class">prefect.agent.kubernetes.agent.KubernetesAgent</p>(name=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/agent/kubernetes/agent.py#L31">[source]</a></span></div>

Agent which deploys flow runs as Kubernetes jobs. Currently this is required to either run on a k8s cluster or on a local machine where the kube_config is pointing at the desired cluster. Information on using the Kubernetes Agent can be found at https://docs.prefect.io/cloud/agent/kubernetes.html

**Args**:     <ul class="args"><li class="args">`name (str, optional)`: An optional name to give this agent. Can also be set through         the environment variable `PREFECT__CLOUD__AGENT__NAME`. Defaults to "agent"</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-agent-kubernetes-agent-kubernetesagent-deploy-flows'><p class="prefect-class">prefect.agent.kubernetes.agent.KubernetesAgent.deploy_flows</p>(flow_runs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/agent/kubernetes/agent.py#L60">[source]</a></span></div>
<p class="methods">Deploy flow runs on to a k8s cluster as jobs<br><br>**Args**:     <ul class="args"><li class="args">`flow_runs (list)`: A list of GraphQLResult flow run objects</li></ul></p>|
 | <div class='method-sig' id='prefect-agent-kubernetes-agent-kubernetesagent-generate-deployment-yaml'><p class="prefect-class">prefect.agent.kubernetes.agent.KubernetesAgent.generate_deployment_yaml</p>(token=None, api=None, namespace=None, image_pull_secrets=None, resource_manager_enabled=False)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/agent/kubernetes/agent.py#L142">[source]</a></span></div>
<p class="methods">Generate and output an installable YAML spec for the agent.<br><br>**Args**:     <ul class="args"><li class="args">`token (str, optional)`: A `RUNNER` token to give the agent     </li><li class="args">`api (str, optional)`: A URL pointing to the Prefect API. Defaults to         `https://api.prefect.io`     </li><li class="args">`namespace (str, optional)`: The namespace to create Prefect jobs in. Defaults         to `default`     </li><li class="args">`image_pull_secrets (str, optional)`: The name of an image pull secret to use         for Prefect jobs     </li><li class="args">`resource_manager_enabled (bool, optional)`: Whether to include the resource         manager as part of the YAML. Defaults to `False`</li></ul>**Returns**:     <ul class="args"><li class="args">`str`: A string representation of the generated YAML</li></ul></p>|
 | <div class='method-sig' id='prefect-agent-kubernetes-agent-kubernetesagent-heartbeat'><p class="prefect-class">prefect.agent.kubernetes.agent.KubernetesAgent.heartbeat</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/agent/kubernetes/agent.py#L219">[source]</a></span></div>
<p class="methods">Write agent heartbeat by opening and closing a heartbeat file. This allows liveness probes to check the agent's main process activity based on the heartbeat file's last modified time.</p>|
 | <div class='method-sig' id='prefect-agent-kubernetes-agent-kubernetesagent-replace-job-spec-yaml'><p class="prefect-class">prefect.agent.kubernetes.agent.KubernetesAgent.replace_job_spec_yaml</p>(flow_run)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/agent/kubernetes/agent.py#L88">[source]</a></span></div>
<p class="methods">Populate metadata and variables in the job_spec.yaml file for flow runs<br><br>**Args**:     <ul class="args"><li class="args">`flow_run (GraphQLResult)`: A flow run object</li></ul>**Returns**:     <ul class="args"><li class="args">`dict`: a dictionary representing the populated yaml object</li></ul></p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on October 17, 2019 at 13:42 UTC</p>