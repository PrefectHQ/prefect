---
sidebarDepth: 2
editLink: false
---
# Docker Tasks
---
Collection of tasks for orchestrating Docker images and containers.

*Note*: If running these tasks from inside of a docker container itself there are some extra
requirements needed for that to work. The container needs to be able to talk to a Docker
server. There are a few ways to accomplish this:

1. Use a base image that has Docker installed and running
    (e.g. https://hub.docker.com/_/docker)
2. Installing the Docker CLI in the base image
3. Talking to an outside (but accessible) Docker API and providing it to the tasks'
    `docker_server_url` parameter

It may also help to run your container (which will run the Prefect Docker tasks) with
extra privileges. (e.g. --privileged=true) and then installing Docker in the container.
 ## BuildImage
 <div class='class-sig' id='prefect-tasks-docker-images-buildimage'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.docker.images.BuildImage</p>(path=None, tag=None, nocache=False, rm=True, forcerm=False, docker_server_url="unix:///var/run/docker.sock", **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/docker/images.py#L373">[source]</a></span></div>

Task for building a Docker image. Note that all initialization arguments can optionally be provided or overwritten at runtime.

**Args**:     <ul class="args"><li class="args">`path (str, optional)`: The path to the directory containing the Dockerfile     </li><li class="args">`tag (str, optional)`: The tag to give the final image     </li><li class="args">`nocache (bool, optional)`: Don't use cache when set to `True`     </li><li class="args">`rm (bool, optional)`: Remove intermediate containers; defaults to `True`     </li><li class="args">`forcerm (bool, optional)`: Always remove intermediate containers, even after         unsuccessful builds; defaults to `False`     </li><li class="args">`docker_server_url (str, optional)`: URL for the Docker server. Defaults to         `unix:///var/run/docker.sock` however other hosts such as `tcp://0.0.0.0:2375`         can be provided     </li><li class="args">`**kwargs (dict, optional)`: additional keyword arguments to pass to the Task         constructor</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-docker-images-buildimage-run'><p class="prefect-class">prefect.tasks.docker.images.BuildImage.run</p>(path=None, tag=None, nocache=False, rm=True, forcerm=False, docker_server_url="unix:///var/run/docker.sock")<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/docker/images.py#L411">[source]</a></span></div>
<p class="methods">Task run method.<br><br>**Args**:     <ul class="args"><li class="args">`path (str, optional)`: The path to the directory containing the Dockerfile     </li><li class="args">`tag (str, optional)`: The tag to give the final image     </li><li class="args">`nocache (bool, optional)`: Don't use cache when set to `True`     </li><li class="args">`rm (bool, optional)`: Remove intermediate containers; defaults to `True`     </li><li class="args">`forcerm (bool, optional)`: Always remove intermediate containers, even after         unsuccessful builds; defaults to `False`     </li><li class="args">`docker_server_url (str, optional)`: URL for the Docker server. Defaults to         `unix:///var/run/docker.sock` however other hosts such as `tcp://0.0.0.0:2375`         can be provided</li></ul>**Returns**:     <ul class="args"><li class="args">`List[dict]`: a cleaned dictionary of the output of `client.build`</li></ul>**Raises**:     <ul class="args"><li class="args">`ValueError`: if either `path` is `None`</li></ul></p>|

---
<br>

 ## ListImages
 <div class='class-sig' id='prefect-tasks-docker-images-listimages'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.docker.images.ListImages</p>(repository_name=None, all_layers=False, docker_server_url="unix:///var/run/docker.sock", **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/docker/images.py#L8">[source]</a></span></div>

Task for listing Docker images. Note that all initialization arguments can optionally be provided or overwritten at runtime.

**Args**:     <ul class="args"><li class="args">`repository_name (str, optional)`: Only show images belonging to this repository;         if not provided then it will list all images from the local Docker server     </li><li class="args">`all_layers (bool, optional)`: Show intermediate image layers     </li><li class="args">`docker_server_url (str, optional)`: URL for the Docker server. Defaults to         `unix:///var/run/docker.sock` however other hosts such as `tcp://0.0.0.0:2375`         can be provided     </li><li class="args">`**kwargs (dict, optional)`: additional keyword arguments to pass to the Task         constructor</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-docker-images-listimages-run'><p class="prefect-class">prefect.tasks.docker.images.ListImages.run</p>(repository_name=None, all_layers=False, docker_server_url="unix:///var/run/docker.sock")<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/docker/images.py#L37">[source]</a></span></div>
<p class="methods">Task run method.<br><br>**Args**:     <ul class="args"><li class="args">`repository_name (str, optional)`: Only show images belonging to this repository;         if not provided then it will list all images from the local Docker server     </li><li class="args">`all_layers (bool, optional)`: Show intermediate image layers     </li><li class="args">`docker_server_url (str, optional)`: URL for the Docker server. Defaults to         `unix:///var/run/docker.sock` however other hosts such as `tcp://0.0.0.0:2375`         can be provided</li></ul>**Returns**:     <ul class="args"><li class="args">`list`: A list of dictionaries containing information about the images found</li></ul></p>|

---
<br>

 ## PullImage
 <div class='class-sig' id='prefect-tasks-docker-images-pullimage'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.docker.images.PullImage</p>(repository=None, tag=None, docker_server_url="unix:///var/run/docker.sock", **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/docker/images.py#L74">[source]</a></span></div>

Task for pulling a Docker image. Note that all initialization arguments can optionally be provided or overwritten at runtime.

**Args**:     <ul class="args"><li class="args">`repository (str, optional)`: The repository to pull the image from     </li><li class="args">`tag (str, optional)`: The tag of the image to pull; if not specified then the         `latest` tag will be pulled     </li><li class="args">`docker_server_url (str, optional)`: URL for the Docker server. Defaults to         `unix:///var/run/docker.sock` however other hosts such as `tcp://0.0.0.0:2375`         can be provided     </li><li class="args">`**kwargs (dict, optional)`: additional keyword arguments to pass to the Task         constructor</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-docker-images-pullimage-run'><p class="prefect-class">prefect.tasks.docker.images.PullImage.run</p>(repository=None, tag=None, docker_server_url="unix:///var/run/docker.sock")<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/docker/images.py#L103">[source]</a></span></div>
<p class="methods">Task run method.<br><br>**Args**:     <ul class="args"><li class="args">`repository (str, optional)`: The repository to pull the image from     </li><li class="args">`tag (str, optional)`: The tag of the image to pull; if not specified then the         `latest` tag will be pulled     </li><li class="args">`docker_server_url (str, optional)`: URL for the Docker server. Defaults to         `unix:///var/run/docker.sock` however other hosts such as `tcp://0.0.0.0:2375`         can be provided</li></ul>**Returns**:     <ul class="args"><li class="args">`str`: The output from Docker for pulling the image</li></ul>**Raises**:     <ul class="args"><li class="args">`ValueError`: if `repository` is `None`</li></ul></p>|

---
<br>

 ## PushImage
 <div class='class-sig' id='prefect-tasks-docker-images-pushimage'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.docker.images.PushImage</p>(repository=None, tag=None, docker_server_url="unix:///var/run/docker.sock", **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/docker/images.py#L150">[source]</a></span></div>

Task for pushing a Docker image. Note that all initialization arguments can optionally be provided or overwritten at runtime.

**Args**:     <ul class="args"><li class="args">`repository (str, optional)`: The repository to push the image to     </li><li class="args">`tag (str, optional)`: The tag for the image to push; if not specified then the         `latest` tag will be pushed     </li><li class="args">`docker_server_url (str, optional)`: URL for the Docker server. Defaults to         `unix:///var/run/docker.sock` however other hosts such as `tcp://0.0.0.0:2375`         can be provided     </li><li class="args">`**kwargs (dict, optional)`: additional keyword arguments to pass to the Task         constructor</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-docker-images-pushimage-run'><p class="prefect-class">prefect.tasks.docker.images.PushImage.run</p>(repository=None, tag=None, docker_server_url="unix:///var/run/docker.sock")<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/docker/images.py#L179">[source]</a></span></div>
<p class="methods">Task run method.<br><br>**Args**:     <ul class="args"><li class="args">`repository (str, optional)`: The repository to push the image to     </li><li class="args">`tag (str, optional)`: The tag for the image to push; if not specified then the         `latest` tag will be pushed     </li><li class="args">`docker_server_url (str, optional)`: URL for the Docker server. Defaults to         `unix:///var/run/docker.sock` however other hosts such as `tcp://0.0.0.0:2375`         can be provided</li></ul>**Returns**:     <ul class="args"><li class="args">`str`: The output from Docker for pushing the image</li></ul>**Raises**:     <ul class="args"><li class="args">`ValueError`: if `repository` is `None`</li></ul></p>|

---
<br>

 ## RemoveImage
 <div class='class-sig' id='prefect-tasks-docker-images-removeimage'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.docker.images.RemoveImage</p>(image=None, force=False, docker_server_url="unix:///var/run/docker.sock", **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/docker/images.py#L225">[source]</a></span></div>

Task for removing a Docker image. Note that all initialization arguments can optionally be provided or overwritten at runtime.

**Args**:     <ul class="args"><li class="args">`image (str, optional)`: The image to remove     </li><li class="args">`force (bool, optional)`: Force removal of the image     </li><li class="args">`docker_server_url (str, optional)`: URL for the Docker server. Defaults to         `unix:///var/run/docker.sock` however other hosts such as `tcp://0.0.0.0:2375`         can be provided     </li><li class="args">`**kwargs (dict, optional)`: additional keyword arguments to pass to the Task         constructor</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-docker-images-removeimage-run'><p class="prefect-class">prefect.tasks.docker.images.RemoveImage.run</p>(image=None, force=False, docker_server_url="unix:///var/run/docker.sock")<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/docker/images.py#L253">[source]</a></span></div>
<p class="methods">Task run method.<br><br>**Args**:     <ul class="args"><li class="args">`image (str, optional)`: The image to remove     </li><li class="args">`force (bool, optional)`: Force removal of the image     </li><li class="args">`docker_server_url (str, optional)`: URL for the Docker server. Defaults to         `unix:///var/run/docker.sock` however other hosts such as `tcp://0.0.0.0:2375`         can be provided</li></ul>**Raises**:     <ul class="args"><li class="args">`ValueError`: if `image` is `None`</li></ul></p>|

---
<br>

 ## TagImage
 <div class='class-sig' id='prefect-tasks-docker-images-tagimage'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.docker.images.TagImage</p>(image=None, repository=None, tag=None, force=False, docker_server_url="unix:///var/run/docker.sock", **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/docker/images.py#L287">[source]</a></span></div>

Task for tagging a Docker image. Note that all initialization arguments can optionally be provided or overwritten at runtime.

**Args**:     <ul class="args"><li class="args">`image (str, optional)`: The image to tag     </li><li class="args">`repository (str, optional)`: The repository to set for the tag     </li><li class="args">`tag (str, optional)`: The tag name for the image     </li><li class="args">`force (bool, optional)`: Force tagging of the image     </li><li class="args">`docker_server_url (str, optional)`: URL for the Docker server. Defaults to         `unix:///var/run/docker.sock` however other hosts such as `tcp://0.0.0.0:2375`         can be provided     </li><li class="args">`**kwargs (dict, optional)`: additional keyword arguments to pass to the Task         constructor</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-docker-images-tagimage-run'><p class="prefect-class">prefect.tasks.docker.images.TagImage.run</p>(image=None, repository=None, tag=None, force=False, docker_server_url="unix:///var/run/docker.sock")<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/docker/images.py#L321">[source]</a></span></div>
<p class="methods">Task run method.<br><br>**Args**:     <ul class="args"><li class="args">`image (str, optional)`: The image to tag     </li><li class="args">`repository (str, optional)`: The repository to set for the tag     </li><li class="args">`tag (str, optional)`: The tag name for the image     </li><li class="args">`force (bool, optional)`: Force tagging of the image     </li><li class="args">`docker_server_url (str, optional)`: URL for the Docker server. Defaults to         `unix:///var/run/docker.sock` however other hosts such as `tcp://0.0.0.0:2375`         can be provided</li></ul>**Returns**:     <ul class="args"><li class="args">`bool`: Whether or not the tagging was successful</li></ul>**Raises**:     <ul class="args"><li class="args">`ValueError`: if either `image` or `repository` are `None`</li></ul></p>|

---
<br>

 ## CreateContainer
 <div class='class-sig' id='prefect-tasks-docker-containers-createcontainer'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.docker.containers.CreateContainer</p>(image_name=None, command=None, detach=False, entrypoint=None, environment=None, docker_server_url="unix:///var/run/docker.sock", **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/docker/containers.py#L8">[source]</a></span></div>

Task for creating a Docker container and optionally running a command. Note that all initialization arguments can optionally be provided or overwritten at runtime.

**Args**:     <ul class="args"><li class="args">`image_name (str, optional)`: Name of the image to run     </li><li class="args">`command (Union[list, str], optional)`: A single command or a list of commands to run     </li><li class="args">`detach (bool, optional)`: Run container in the background     </li><li class="args">`entrypoint (Union[str, list])`: The entrypoint for the container     </li><li class="args">`environment (Union[dict, list])`: Environment variables to set inside the container,         as a dictionary or a list of strings in the format ["SOMEVARIABLE=xxx"].     </li><li class="args">`docker_server_url (str, optional)`: URL for the Docker server. Defaults to         `unix:///var/run/docker.sock` however other hosts such as `tcp://0.0.0.0:2375`         can be provided     </li><li class="args">`**kwargs (dict, optional)`: additional keyword arguments to pass to the Task         constructor</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-docker-containers-createcontainer-run'><p class="prefect-class">prefect.tasks.docker.containers.CreateContainer.run</p>(image_name=None, command=None, detach=False, entrypoint=None, environment=None, docker_server_url="unix:///var/run/docker.sock")<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/docker/containers.py#L46">[source]</a></span></div>
<p class="methods">Task run method.<br><br>**Args**:     <ul class="args"><li class="args">`image_name (str, optional)`: Name of the image to run     </li><li class="args">`command (Union[list, str], optional)`: A single command or a list of commands to run     </li><li class="args">`detach (bool, optional)`: Run container in the background     </li><li class="args">`entrypoint (Union[str, list])`: The entrypoint for the container     </li><li class="args">`environment (Union[dict, list])`: Environment variables to set inside the container,         as a dictionary or a list of strings in the format ["SOMEVARIABLE=xxx"].     </li><li class="args">`docker_server_url (str, optional)`: URL for the Docker server. Defaults to         `unix:///var/run/docker.sock` however other hosts such as `tcp://0.0.0.0:2375`         can be provided</li></ul>**Returns**:     <ul class="args"><li class="args">`str`: A string representing the container id</li></ul>**Raises**:     <ul class="args"><li class="args">`ValueError`: if `image_name` is `None`</li></ul></p>|

---
<br>

 ## GetContainerLogs
 <div class='class-sig' id='prefect-tasks-docker-containers-getcontainerlogs'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.docker.containers.GetContainerLogs</p>(container_id=None, docker_server_url="unix:///var/run/docker.sock", **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/docker/containers.py#L110">[source]</a></span></div>

Task for getting the logs of a Docker container. *Note:* This does not stream logs. Note that all initialization arguments can optionally be provided or overwritten at runtime.

**Args**:     <ul class="args"><li class="args">`container_id (str, optional)`: The id of a container to retrieve logs from     </li><li class="args">`docker_server_url (str, optional)`: URL for the Docker server. Defaults to         `unix:///var/run/docker.sock` however other hosts such as `tcp://0.0.0.0:2375`         can be provided     </li><li class="args">`**kwargs (dict, optional)`: additional keyword arguments to pass to the Task         constructor</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-docker-containers-getcontainerlogs-run'><p class="prefect-class">prefect.tasks.docker.containers.GetContainerLogs.run</p>(container_id=None, docker_server_url="unix:///var/run/docker.sock")<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/docker/containers.py#L135">[source]</a></span></div>
<p class="methods">Task run method.<br><br>**Args**:     <ul class="args"><li class="args">`container_id (str, optional)`: The id of a container to retrieve logs from     </li><li class="args">`docker_server_url (str, optional)`: URL for the Docker server. Defaults to         `unix:///var/run/docker.sock` however other hosts such as `tcp://0.0.0.0:2375`         can be provided</li></ul>**Returns**:     <ul class="args"><li class="args">`str`: A string representation of the logs from the container</li></ul>**Raises**:     <ul class="args"><li class="args">`ValueError`: if `container_id` is `None`</li></ul></p>|

---
<br>

 ## ListContainers
 <div class='class-sig' id='prefect-tasks-docker-containers-listcontainers'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.docker.containers.ListContainers</p>(all_containers=False, docker_server_url="unix:///var/run/docker.sock", **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/docker/containers.py#L179">[source]</a></span></div>

Task for listing Docker containers. Note that all initialization arguments can optionally be provided or overwritten at runtime.

**Args**:     <ul class="args"><li class="args">`all_containers (bool, optional)`: Show all containers. Only running containers are shown by default     </li><li class="args">`docker_server_url (str, optional)`: URL for the Docker server. Defaults to         `unix:///var/run/docker.sock` however other hosts such as `tcp://0.0.0.0:2375`         can be provided     </li><li class="args">`**kwargs (dict, optional)`: additional keyword arguments to pass to the Task         constructor</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-docker-containers-listcontainers-run'><p class="prefect-class">prefect.tasks.docker.containers.ListContainers.run</p>(all_containers=False, docker_server_url="unix:///var/run/docker.sock")<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/docker/containers.py#L204">[source]</a></span></div>
<p class="methods">Task run method.<br><br>**Args**:     <ul class="args"><li class="args">`all_containers (bool, optional)`: Show all containers. Only running containers are shown by default     </li><li class="args">`docker_server_url (str, optional)`: URL for the Docker server. Defaults to         `unix:///var/run/docker.sock` however other hosts such as `tcp://0.0.0.0:2375`         can be provided</li></ul>**Returns**:     <ul class="args"><li class="args">`list`: A list of dicts, one per container</li></ul></p>|

---
<br>

 ## StartContainer
 <div class='class-sig' id='prefect-tasks-docker-containers-startcontainer'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.docker.containers.StartContainer</p>(container_id=None, docker_server_url="unix:///var/run/docker.sock", **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/docker/containers.py#L233">[source]</a></span></div>

Task for starting a Docker container that runs the (optional) command it was created with. Note that all initialization arguments can optionally be provided or overwritten at runtime.

**Args**:     <ul class="args"><li class="args">`container_id (str, optional)`: The id of a container to start     </li><li class="args">`docker_server_url (str, optional)`: URL for the Docker server. Defaults to         `unix:///var/run/docker.sock` however other hosts such as `tcp://0.0.0.0:2375`         can be provided     </li><li class="args">`**kwargs (dict, optional)`: additional keyword arguments to pass to the Task         constructor</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-docker-containers-startcontainer-run'><p class="prefect-class">prefect.tasks.docker.containers.StartContainer.run</p>(container_id=None, docker_server_url="unix:///var/run/docker.sock")<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/docker/containers.py#L258">[source]</a></span></div>
<p class="methods">Task run method.<br><br>**Args**:     <ul class="args"><li class="args">`container_id (str, optional)`: The id of a container to start     </li><li class="args">`docker_server_url (str, optional)`: URL for the Docker server. Defaults to         `unix:///var/run/docker.sock` however other hosts such as `tcp://0.0.0.0:2375`         can be provided</li></ul>**Raises**:     <ul class="args"><li class="args">`ValueError`: if `container_id` is `None`</li></ul></p>|

---
<br>

 ## StopContainer
 <div class='class-sig' id='prefect-tasks-docker-containers-stopcontainer'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.docker.containers.StopContainer</p>(container_id=None, docker_server_url="unix:///var/run/docker.sock", **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/docker/containers.py#L292">[source]</a></span></div>

Task for stopping a Docker container. Note that all initialization arguments can optionally be provided or overwritten at runtime.

**Args**:     <ul class="args"><li class="args">`container_id (str, optional)`: The id of a container to stop     </li><li class="args">`docker_server_url (str, optional)`: URL for the Docker server. Defaults to         `unix:///var/run/docker.sock` however other hosts such as `tcp://0.0.0.0:2375`         can be provided     </li><li class="args">`**kwargs (dict, optional)`: additional keyword arguments to pass to the Task         constructor</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-docker-containers-stopcontainer-run'><p class="prefect-class">prefect.tasks.docker.containers.StopContainer.run</p>(container_id=None, docker_server_url="unix:///var/run/docker.sock")<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/docker/containers.py#L317">[source]</a></span></div>
<p class="methods">Task run method.<br><br>**Args**:     <ul class="args"><li class="args">`container_id (str, optional)`: The id of a container to stop     </li><li class="args">`docker_server_url (str, optional)`: URL for the Docker server. Defaults to         `unix:///var/run/docker.sock` however other hosts such as `tcp://0.0.0.0:2375`         can be provided</li></ul>**Raises**:     <ul class="args"><li class="args">`ValueError`: if `container_id` is `None`</li></ul></p>|

---
<br>

 ## WaitOnContainer
 <div class='class-sig' id='prefect-tasks-docker-containers-waitoncontainer'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.docker.containers.WaitOnContainer</p>(container_id=None, docker_server_url="unix:///var/run/docker.sock", raise_on_exit_code=True, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/docker/containers.py#L351">[source]</a></span></div>

Task for waiting on an already started Docker container. Note that all initialization arguments can optionally be provided or overwritten at runtime.

**Args**:     <ul class="args"><li class="args">`container_id (str, optional)`: The id of a container to start     </li><li class="args">`docker_server_url (str, optional)`: URL for the Docker server. Defaults to         `unix:///var/run/docker.sock` however other hosts such as `tcp://0.0.0.0:2375`         can be provided     </li><li class="args">`raise_on_exit_code (bool, optional)`: whether to raise a `FAIL` signal for a nonzero exit code;         defaults to `True`     </li><li class="args">`**kwargs (dict, optional)`: additional keyword arguments to pass to the Task         constructor</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-docker-containers-waitoncontainer-run'><p class="prefect-class">prefect.tasks.docker.containers.WaitOnContainer.run</p>(container_id=None, docker_server_url="unix:///var/run/docker.sock", raise_on_exit_code=True)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/docker/containers.py#L380">[source]</a></span></div>
<p class="methods">Task run method.<br><br>**Args**:     <ul class="args"><li class="args">`container_id (str, optional)`: The id of a container to wait on     </li><li class="args">`docker_server_url (str, optional)`: URL for the Docker server. Defaults to         `unix:///var/run/docker.sock` however other hosts such as `tcp://0.0.0.0:2375`         can be provided     </li><li class="args">`raise_on_exit_code (bool, optional)`: whether to raise a `FAIL` signal for a nonzero exit code;         defaults to `True`</li></ul>**Returns**:     <ul class="args"><li class="args">`dict`: a dictionary with `StatusCode` and `Error` keys</li></ul>**Raises**:     <ul class="args"><li class="args">`ValueError`: if `container_id` is `None`     </li><li class="args">`FAIL`: if `raise_on_exit_code` is `True` and the container exits with a nonzero exit code</li></ul></p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on March 30, 2020 at 17:55 UTC</p>