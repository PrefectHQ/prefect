---
sidebarDepth: 2
editLink: false
---
# DockerOnKubernetes Environment
---
 ## DockerOnKubernetesEnvironment
 <div class='class-sig' id='prefect-environments-kubernetes-docker-docker-on-kubernetes-dockeronkubernetesenvironment'><p class="prefect-sig">class </p><p class="prefect-class">prefect.environments.kubernetes.docker.docker_on_kubernetes.DockerOnKubernetesEnvironment</p>(base_image="python:3.6", registry_url=None, python_dependencies=None, image_name=None, image_tag=None, env_vars=None, files=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/kubernetes/docker/docker_on_kubernetes.py#L13">[source]</a></span></div>

DockerOnKubernetes is an environment which deploys your image of choice on Kubernetes. *Note*: Make sure the base image is able to pip install Prefect. The default image for this environment is Python 3.6.

(A future environment will allow for a minimal set up which does not require pip)

There are no set up requirements, and execute creates a single job that has the role of running the flow. The job created in the execute function does have the requirement in that it needs to have an `identifier_label` set with a UUID so resources can be cleaned up independently of other deployments.

**Args**:     <ul class="args"><li class="args">`base_image (string, optional)`: the base image for this environment (e.g. `python:3.6`), defaults to `python:3.6`     </li><li class="args">`registry_url (string, optional)`: URL of a registry to push the image to; image will not be pushed if not provided     </li><li class="args">`python_dependencies (List[str], optional)`: list of pip installable dependencies for the image     </li><li class="args">`image_name (string, optional)`: name of the image to use when building, defaults to a UUID     </li><li class="args">`image_tag (string, optional)`: tag of the image to use when building, defaults to a UUID     </li><li class="args">`env_vars (dict, optional)`: a dictionary of environment variables to use when building     </li><li class="args">`files (dict, optional)`: a dictionary of files to copy into the image when building</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-environments-kubernetes-docker-docker-on-kubernetes-dockeronkubernetesenvironment-build'><p class="prefect-class">prefect.environments.kubernetes.docker.docker_on_kubernetes.DockerOnKubernetesEnvironment.build</p>(flow, push=True)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/kubernetes/docker/docker_on_kubernetes.py#L120">[source]</a></span></div>
<p class="methods">Build the Docker container. Returns a DockerEnvironment with the appropriate image_name and image_tag set.<br><br>**Args**:     <ul class="args"><li class="args">`flow (prefect.Flow)`: Flow to be placed in container     </li><li class="args">`push (bool)`: Whether or not to push to registry after build</li></ul>**Returns**:     <ul class="args"><li class="args">`DockerEnvironment`: a DockerEnvironment that represents the provided flow.</li></ul></p>|
 | <div class='method-sig' id='prefect-environments-kubernetes-docker-docker-on-kubernetes-dockeronkubernetesenvironment-execute'><p class="prefect-class">prefect.environments.kubernetes.docker.docker_on_kubernetes.DockerOnKubernetesEnvironment.execute</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/kubernetes/docker/docker_on_kubernetes.py#L94">[source]</a></span></div>
<p class="methods">Create a single Kubernetes job on the default namespace that runs a flow</p>|
 | <div class='method-sig' id='prefect-environments-kubernetes-docker-docker-on-kubernetes-dockeronkubernetesenvironment-setup'><p class="prefect-class">prefect.environments.kubernetes.docker.docker_on_kubernetes.DockerOnKubernetesEnvironment.setup</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/kubernetes/docker/docker_on_kubernetes.py#L114">[source]</a></span></div>
<p class="methods">No setup is required for this environment</p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>by Prefect 0.5.1+0.g71829f4e.dirty on April 4, 2019 at 23:56 UTC</p>