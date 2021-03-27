---
sidebarDepth: 2
editLink: false
---
# Storage
---
The Prefect Storage interface encapsulates logic for storing, serializing and even running Flows.
Each storage unit is able to store _multiple_ flows (possibly with the constraint of name uniqueness
within a given unit), and exposes the following methods and attributes:

- a `flows` attribute that is a dictionary of flow name  -> location
- an `add_flow(flow: Flow) -> str` method for adding flows to Storage, and that will return the intended
location of the given flow in the Storage unit (note flow uploading/saving does not happen until `build`)
- the `__contains__(self, obj) -> bool` special method for determining whether the Storage contains a
given Flow
- one of `get_flow(flow_location: str)` for retrieving a way of interfacing with either `flow.run` or a
`FlowRunner` for the flow
- a `build() -> Storage` method for "building" the storage. In storage options where flows are stored in
an external service (such as S3 and the filesystem) the flows are uploaded/saved during this step
- a `serialize() -> dict` method for serializing the relevant information about this Storage for later
re-use.

The default flow storage mechanism is based on pickling the flow object using `cloudpickle` and the
saving that pickle to a location. Flows can optionally also be stored as a script using the
`stored_as_script` boolean kwarg. For more information visit the
[file-based storage idiom](/core/idioms/file-based.html).
 ## Storage
 <div class='class-sig' id='prefect-environments-storage-base-storage'><p class="prefect-sig">class </p><p class="prefect-class">prefect.environments.storage.base.Storage</p>(result=None, secrets=None, labels=None, add_default_labels=None, stored_as_script=False)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/storage/base.py#L15">[source]</a></span></div>

Base interface for Storage objects. All kwargs present in this base class are valid on storage subclasses.

**Args**:     <ul class="args"><li class="args">`result (Result, optional)`: a default result to use for         all flows which utilize this storage class     </li><li class="args">`secrets (List[str], optional)`: a list of Prefect Secrets which will be used to         populate `prefect.context` for each flow run.  Used primarily for providing         authentication credentials.     </li><li class="args">`labels (List[str], optional)`: a list of labels to associate with this `Storage`.     </li><li class="args">`add_default_labels (bool)`: If `True`, adds the storage specific default label (if         applicable) to the storage labels. Defaults to the value specified in the         configuration at `flows.defaults.storage.add_default_labels`.     </li><li class="args">`stored_as_script (bool, optional)`: boolean for specifying if the flow has been stored         as a `.py` file. Defaults to `False`</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-environments-storage-base-storage-add-flow'><p class="prefect-class">prefect.environments.storage.base.Storage.add_flow</p>(flow)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/storage/base.py#L103">[source]</a></span></div>
<p class="methods">Method for adding a new flow to this Storage object.<br><br>**Args**:     <ul class="args"><li class="args">`flow (Flow)`: a Prefect Flow to add</li></ul> **Returns**:     <ul class="args"><li class="args">`str`: the location of the newly added flow in this Storage object</li></ul></p>|
 | <div class='method-sig' id='prefect-environments-storage-base-storage-build'><p class="prefect-class">prefect.environments.storage.base.Storage.build</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/storage/base.py#L135">[source]</a></span></div>
<p class="methods">Build the Storage object.<br><br>**Returns**:     <ul class="args"><li class="args">`Storage`: a Storage object that contains information about how and where         each flow is stored</li></ul></p>|
 | <div class='method-sig' id='prefect-environments-storage-base-storage-get-env-runner'><p class="prefect-class">prefect.environments.storage.base.Storage.get_env_runner</p>(flow_location)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/storage/base.py#L76">[source]</a></span></div>
<p class="methods">Given a `flow_location` within this Storage object, returns something with a `run()` method that accepts a collection of environment variables for running the flow; for example, to specify an executor you would need to provide `{'PREFECT__ENGINE__EXECUTOR': ...}`.<br><br>**Args**:     <ul class="args"><li class="args">`flow_location (str)`: the location of a flow within this Storage</li></ul> **Returns**:     <ul class="args"><li class="args">a runner interface (something with a `run()` method for running the flow)</li></ul></p>|
 | <div class='method-sig' id='prefect-environments-storage-base-storage-get-flow'><p class="prefect-class">prefect.environments.storage.base.Storage.get_flow</p>(flow_location)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/storage/base.py#L91">[source]</a></span></div>
<p class="methods">Given a flow_location within this Storage object, returns the underlying Flow (if possible).<br><br>**Args**:     <ul class="args"><li class="args">`flow_location (str)`: the location of a flow within this Storage</li></ul> **Returns**:     <ul class="args"><li class="args">`Flow`: the requested flow</li></ul></p>|
 | <div class='method-sig' id='prefect-environments-storage-base-storage-run-basic-healthchecks'><p class="prefect-class">prefect.environments.storage.base.Storage.run_basic_healthchecks</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/storage/base.py#L156">[source]</a></span></div>
<p class="methods">Runs basic healthchecks on the flows contained in this Storage class</p>|
 | <div class='method-sig' id='prefect-environments-storage-base-storage-serialize'><p class="prefect-class">prefect.environments.storage.base.Storage.serialize</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/storage/base.py#L146">[source]</a></span></div>
<p class="methods">Returns a serialized version of the Storage object<br><br>**Returns**:     <ul class="args"><li class="args">`dict`: the serialized Storage</li></ul></p>|

---
<br>

 ## Docker
 <div class='class-sig' id='prefect-environments-storage-docker-docker'><p class="prefect-sig">class </p><p class="prefect-class">prefect.environments.storage.docker.Docker</p>(registry_url=None, base_image=None, dockerfile=None, python_dependencies=None, image_name=None, image_tag=None, env_vars=None, files=None, prefect_version=None, local_image=False, ignore_healthchecks=False, base_url=None, tls_config=False, build_kwargs=None, prefect_directory="/opt/prefect", path=None, stored_as_script=False, extra_dockerfile_commands=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/storage/docker.py#L34">[source]</a></span></div>

Docker storage provides a mechanism for storing Prefect flows in Docker images and optionally pushing them to a registry.

A user specifies a `registry_url`, `base_image` and other optional dependencies (e.g., `python_dependencies`) and `build()` will create a temporary Dockerfile that is used to build the image.

Note that the `base_image` must be capable of `pip` installing.  Note that registry behavior with respect to image names can differ between providers - for example, Google's GCR registry allows for registry URLs of the form `gcr.io/my-registry/subdir/my-image-name` whereas DockerHub requires the registry URL to be separate from the image name.

Custom modules can be packaged up during build by attaching the files and setting the `PYTHONPATH` to the location of those files. Otherwise the modules can be set independently when using a custom base image prior to the build here.


```python
Docker(
    files={
        # absolute path source -> destination in image
        "/Users/me/code/mod1.py": "/modules/mod1.py",
        "/Users/me/code/mod2.py": "/modules/mod2.py",
    },
    env_vars={
        # append modules directory to PYTHONPATH
        "PYTHONPATH": "$PYTHONPATH:modules/"
    },
)

```

**Args**:     <ul class="args"><li class="args">`registry_url (str, optional)`: URL of a registry to push the image to;         image will not be pushed if not provided     </li><li class="args">`base_image (str, optional)`: the base image for this environment (e.g.         `python:3.6`), defaults to the `prefecthq/prefect` image matching your         python version and prefect core library version used at runtime.     </li><li class="args">`dockerfile (str, optional)`: a path to a Dockerfile to use in building         this storage; note that, if provided, your present working directory         will be used as the build context     </li><li class="args">`python_dependencies (List[str], optional)`: list of pip installable         dependencies for the image     </li><li class="args">`image_name (str, optional)`: name of the image to use when building,         populated with a UUID after build     </li><li class="args">`image_tag (str, optional)`: tag of the image to use when building,         populated with a UUID after build     </li><li class="args">`env_vars (dict, optional)`: a dictionary of environment variables to         use when building     </li><li class="args">`files (dict, optional)`: a dictionary of files or directories to copy into         the image when building. Takes the format of `{'src': 'dest'}`     </li><li class="args">`prefect_version (str, optional)`: an optional branch, tag, or commit         specifying the version of prefect you want installed into the container;         defaults to the version you are currently using or `"master"` if your         version is ahead of the latest tag     </li><li class="args">`local_image (bool, optional)`: an optional flag whether or not to use a         local docker image, if True then a pull will not be attempted     </li><li class="args">`ignore_healthchecks (bool, optional)`: if True, the Docker healthchecks         are not added to the Dockerfile. If False (default), healthchecks         are included.     </li><li class="args">`base_url (str, optional)`: a URL of a Docker daemon to use when for         Docker related functionality.  Defaults to DOCKER_HOST env var if not set     </li><li class="args">`tls_config (Union[bool, docker.tls.TLSConfig], optional)`: a TLS configuration to pass         to the Docker client.         [Documentation](https://docker-py.readthedocs.io/en/stable/tls.html#docker.tls.TLSConfig)     </li><li class="args">`build_kwargs (dict, optional)`: Additional keyword arguments to pass to Docker's build         step. [Documentation](https://docker-py.readthedocs.io/en/stable/         api.html#docker.api.build.BuildApiMixin.build)     </li><li class="args">`prefect_directory (str, optional)`: Path to the directory where prefect configuration/flows          should be stored inside the Docker image. Defaults to `/opt/prefect`.     </li><li class="args">`path (str, optional)`: a direct path to the location of the flow file in the Docker image         if `stored_as_script=True`.     </li><li class="args">`stored_as_script (bool, optional)`: boolean for specifying if the flow has been stored         as a `.py` file. Defaults to `False`     </li><li class="args">`extra_dockerfile_commands (list[str], optional)`: list of Docker build commands         which are injected at the end of generated DockerFile (before the health checks).         Defaults to `None`     </li><li class="args">`**kwargs (Any, optional)`: any additional `Storage` initialization options</li></ul> **Raises**:     <ul class="args"><li class="args">`ValueError`: if both `base_image` and `dockerfile` are provided</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-environments-storage-docker-docker-add-flow'><p class="prefect-class">prefect.environments.storage.docker.Docker.add_flow</p>(flow)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/storage/docker.py#L261">[source]</a></span></div>
<p class="methods">Method for adding a new flow to this Storage object.<br><br>**Args**:     <ul class="args"><li class="args">`flow (Flow)`: a Prefect Flow to add</li></ul> **Returns**:     <ul class="args"><li class="args">`str`: the location of the newly added flow in this Storage object</li></ul></p>|
 | <div class='method-sig' id='prefect-environments-storage-docker-docker-build'><p class="prefect-class">prefect.environments.storage.docker.Docker.build</p>(push=True)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/storage/docker.py#L336">[source]</a></span></div>
<p class="methods">Build the Docker storage object.  If image name and tag are not set, they will be autogenerated.<br><br>**Args**:     <ul class="args"><li class="args">`push (bool, optional)`: Whether or not to push the built Docker image, this         requires the `registry_url` to be set</li></ul> **Returns**:     <ul class="args"><li class="args">`Docker`: a new Docker storage object that contains information about how and         where the flow is stored. Image name and tag are generated during the         build process.</li></ul> **Raises**:     <ul class="args"><li class="args">`InterruptedError`: if either pushing or pulling the image fails</li></ul></p>|
 | <div class='method-sig' id='prefect-environments-storage-docker-docker-create-dockerfile-object'><p class="prefect-class">prefect.environments.storage.docker.Docker.create_dockerfile_object</p>(directory)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/storage/docker.py#L447">[source]</a></span></div>
<p class="methods">Writes a dockerfile to the provided directory using the specified arguments on this Docker storage object.<br><br>In order for the docker python library to build a container it needs a Dockerfile that it can use to define the container. This function takes the specified arguments then writes them to a temporary file called Dockerfile.<br><br>*Note*: if `files` are added to this container, they will be copied to this directory as well.<br><br>**Args**:     <ul class="args"><li class="args">`directory (str)`: A directory where the Dockerfile will be created</li></ul> **Returns**:     <ul class="args"><li class="args">`str`: the absolute file path to the Dockerfile</li></ul></p>|
 | <div class='method-sig' id='prefect-environments-storage-docker-docker-get-env-runner'><p class="prefect-class">prefect.environments.storage.docker.Docker.get_env_runner</p>(flow_location)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/storage/docker.py#L220">[source]</a></span></div>
<p class="methods">Given a flow_location within this Storage object, returns something with a `run()` method which accepts the standard runner kwargs and can run the flow.<br><br>**Args**:     <ul class="args"><li class="args">`flow_location (str)`: the location of a flow within this Storage</li></ul> **Returns**:     <ul class="args"><li class="args">a runner interface (something with a `run()` method for running the flow)</li></ul></p>|
 | <div class='method-sig' id='prefect-environments-storage-docker-docker-get-flow'><p class="prefect-class">prefect.environments.storage.docker.Docker.get_flow</p>(flow_location=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/storage/docker.py#L284">[source]</a></span></div>
<p class="methods">Given a file path within this Docker container, returns the underlying Flow. Note that this method should only be run _within_ the container itself.<br><br>**Args**:     <ul class="args"><li class="args">`flow_location (str, optional)`: the file path of a flow within this container. Will use         `path` if not provided.</li></ul> **Returns**:     <ul class="args"><li class="args">`Flow`: the requested flow</li></ul> **Raises**:     <ul class="args"><li class="args">`ValueError`: if the flow is not contained in this storage</li></ul></p>|
 | <div class='method-sig' id='prefect-environments-storage-docker-docker-pull-image'><p class="prefect-class">prefect.environments.storage.docker.Docker.pull_image</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/storage/docker.py#L605">[source]</a></span></div>
<p class="methods">Pull the image specified so it can be built.<br><br>In order for the docker python library to use a base image it must be pulled from either the main docker registry or a separate registry that must be set as `registry_url` on this class.<br><br>**Raises**:     <ul class="args"><li class="args">`InterruptedError`: if either pulling the image fails</li></ul></p>|
 | <div class='method-sig' id='prefect-environments-storage-docker-docker-push-image'><p class="prefect-class">prefect.environments.storage.docker.Docker.push_image</p>(image_name, image_tag)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/storage/docker.py#L625">[source]</a></span></div>
<p class="methods">Push this environment to a registry<br><br>**Args**:     <ul class="args"><li class="args">`image_name (str)`: Name for the image     </li><li class="args">`image_tag (str)`: Tag for the image</li></ul> **Raises**:     <ul class="args"><li class="args">`InterruptedError`: if either pushing the image fails</li></ul></p>|

---
<br>

 ## Local
 <div class='class-sig' id='prefect-environments-storage-local-local'><p class="prefect-sig">class </p><p class="prefect-class">prefect.environments.storage.local.Local</p>(directory=None, validate=True, path=None, stored_as_script=False, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/storage/local.py#L16">[source]</a></span></div>

Local storage class.  This class represents the Storage interface for Flows stored as bytes in the local filesystem.

Note that if you register a Flow with Prefect Cloud using this storage, your flow's environment will automatically be labeled with your machine's hostname. This ensures that only agents that are known to be running on the same filesystem can run your flow.

**Args**:     <ul class="args"><li class="args">`directory (str, optional)`: the directory the flows will be stored in;         defaults to `~/.prefect/flows`.  If it doesn't already exist, it will be         created for you.     </li><li class="args">`validate (bool, optional)`: a boolean specifying whether to validate the         provided directory path; if `True`, the directory will be converted to an         absolute path and created.  Defaults to `True`     </li><li class="args">`path (str, optional)`: a direct path to the location of the flow file if         `stored_as_script=True`, otherwise this path will be used when storing the serialized,         pickled flow. If `stored_as_script=True`, the direct path may be a file path         (such as 'path/to/myflow.py') or a direct python path (such as 'myrepo.mymodule.myflow')     </li><li class="args">`stored_as_script (bool, optional)`: boolean for specifying if the flow has been stored         as a `.py` file. Defaults to `False`     </li><li class="args">`**kwargs (Any, optional)`: any additional `Storage` initialization options</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-environments-storage-local-local-add-flow'><p class="prefect-class">prefect.environments.storage.local.Local.add_flow</p>(flow)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/storage/local.py#L110">[source]</a></span></div>
<p class="methods">Method for storing a new flow as bytes in the local filesytem.<br><br>**Args**:     <ul class="args"><li class="args">`flow (Flow)`: a Prefect Flow to add</li></ul> **Returns**:     <ul class="args"><li class="args">`str`: the location of the newly added flow in this Storage object</li></ul> **Raises**:     <ul class="args"><li class="args">`ValueError`: if a flow with the same name is already contained in this storage</li></ul></p>|
 | <div class='method-sig' id='prefect-environments-storage-local-local-build'><p class="prefect-class">prefect.environments.storage.local.Local.build</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/storage/local.py#L157">[source]</a></span></div>
<p class="methods">Build the Storage object.<br><br>**Returns**:     <ul class="args"><li class="args">`Storage`: a Storage object that contains information about how and where         each flow is stored</li></ul></p>|
 | <div class='method-sig' id='prefect-environments-storage-local-local-get-flow'><p class="prefect-class">prefect.environments.storage.local.Local.get_flow</p>(flow_location=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/storage/local.py#L73">[source]</a></span></div>
<p class="methods">Given a flow_location within this Storage object, returns the underlying Flow (if possible).<br><br>**Args**:     <ul class="args"><li class="args">`flow_location (str, optional)`: the location of a flow within this Storage; in this case,         a file path or python path where a Flow has been serialized to. Will use `path`         if not provided.</li></ul> **Returns**:     <ul class="args"><li class="args">`Flow`: the requested flow</li></ul> **Raises**:     <ul class="args"><li class="args">`ValueError`: if the flow is not contained in this storage</li></ul></p>|

---
<br>

 ## S3
 <div class='class-sig' id='prefect-environments-storage-s3-s3'><p class="prefect-sig">class </p><p class="prefect-class">prefect.environments.storage.s3.S3</p>(bucket, key=None, stored_as_script=False, local_script_path=None, client_options=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/storage/s3.py#L17">[source]</a></span></div>

S3 storage class.  This class represents the Storage interface for Flows stored as bytes in an S3 bucket.

This storage class optionally takes a `key` which will be the name of the Flow object when stored in S3. If this key is not provided the Flow upload name will take the form `slugified-flow-name/slugified-current-timestamp`.

**Note**: Flows registered with this Storage option will automatically be  labeled with `s3-flow-storage`.

**Args**:     <ul class="args"><li class="args">`bucket (str)`: the name of the S3 Bucket to store Flows     </li><li class="args">`key (str, optional)`: a unique key to use for uploading a Flow to S3. This         is only useful when storing a single Flow using this storage object.     </li><li class="args">`stored_as_script (bool, optional)`: boolean for specifying if the flow has been stored         as a `.py` file. Defaults to `False`     </li><li class="args">`local_script_path (str, optional)`: the path to a local script to upload when `stored_as_script`         is set to `True`. If not set then the value of `local_script_path` from `prefect.context` is         used. If neither are set then script will not be uploaded and users should manually place the         script file in the desired `key` location in an S3 bucket.     </li><li class="args">`client_options (dict, optional)`: Additional options for the `boto3` client.     </li><li class="args">`**kwargs (Any, optional)`: any additional `Storage` initialization options</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-environments-storage-s3-s3-add-flow'><p class="prefect-class">prefect.environments.storage.s3.S3.add_flow</p>(flow)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/storage/s3.py#L121">[source]</a></span></div>
<p class="methods">Method for storing a new flow as bytes in the local filesytem.<br><br>**Args**:     <ul class="args"><li class="args">`flow (Flow)`: a Prefect Flow to add</li></ul> **Returns**:     <ul class="args"><li class="args">`str`: the location of the newly added flow in this Storage object</li></ul> **Raises**:     <ul class="args"><li class="args">`ValueError`: if a flow with the same name is already contained in this storage</li></ul></p>|
 | <div class='method-sig' id='prefect-environments-storage-s3-s3-build'><p class="prefect-class">prefect.environments.storage.s3.S3.build</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/storage/s3.py#L154">[source]</a></span></div>
<p class="methods">Build the S3 storage object by uploading Flows to an S3 bucket. This will upload all of the flows found in `storage.flows`. If there is an issue uploading to the S3 bucket an error will be logged.<br><br>**Returns**:     <ul class="args"><li class="args">`Storage`: an S3 object that contains information about how and where         each flow is stored</li></ul> **Raises**:     <ul class="args"><li class="args">`botocore.ClientError`: if there is an issue uploading a Flow to S3</li></ul></p>|
 | <div class='method-sig' id='prefect-environments-storage-s3-s3-get-flow'><p class="prefect-class">prefect.environments.storage.s3.S3.get_flow</p>(flow_location=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/storage/s3.py#L73">[source]</a></span></div>
<p class="methods">Given a flow_location within this Storage object or S3, returns the underlying Flow (if possible).<br><br>**Args**:     <ul class="args"><li class="args">`flow_location (str, optional)`: the location of a flow within this Storage; in this case         an S3 object key where a Flow has been serialized to. Will use `key` if not provided.</li></ul> **Returns**:     <ul class="args"><li class="args">`Flow`: the requested Flow</li></ul> **Raises**:     <ul class="args"><li class="args">`ValueError`: if the flow is not contained in this storage     </li><li class="args">`botocore.ClientError`: if there is an issue downloading the Flow from S3</li></ul></p>|

---
<br>

 ## GCS
 <div class='class-sig' id='prefect-environments-storage-gcs-gcs'><p class="prefect-sig">class </p><p class="prefect-class">prefect.environments.storage.gcs.GCS</p>(bucket, key=None, project=None, stored_as_script=False, local_script_path=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/storage/gcs.py#L17">[source]</a></span></div>

GoogleCloudStorage storage class.  This class represents the Storage interface for Flows stored as bytes in an GCS bucket.  To authenticate with Google Cloud, you need to ensure that your Prefect Agent has the proper credentials available (see https://cloud.google.com/docs/authentication/production for all the authentication options).

This storage class optionally takes a `key` which will be the name of the Flow object when stored in GCS. If this key is not provided the Flow upload name will take the form `slugified-flow-name/slugified-current-timestamp`.

**Note**: Flows registered with this Storage option will automatically be  labeled with `gcs-flow-storage`.

**Args**:     <ul class="args"><li class="args">`bucket (str, optional)`: the name of the GCS Bucket to store the Flow     </li><li class="args">`key (str, optional)`: a unique key to use for uploading this Flow to GCS. This         is only useful when storing a single Flow using this storage object.     </li><li class="args">`project (str, optional)`: the google project where any GCS API requests are billed to;         if not provided, the project will be inferred from your Google Cloud credentials.     </li><li class="args">`stored_as_script (bool, optional)`: boolean for specifying if the flow has been stored         as a `.py` file. Defaults to `False`     </li><li class="args">`local_script_path (str, optional)`: the path to a local script to upload when `stored_as_script`         is set to `True`. If not set then the value of `local_script_path` from `prefect.context` is         used. If neither are set then script will not be uploaded and users should manually place the         script file in the desired `key` location in a GCS bucket.     </li><li class="args">`**kwargs (Any, optional)`: any additional `Storage` initialization options</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-environments-storage-gcs-gcs-add-flow'><p class="prefect-class">prefect.environments.storage.gcs.GCS.add_flow</p>(flow)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/storage/gcs.py#L113">[source]</a></span></div>
<p class="methods">Method for storing a new flow as bytes in a GCS bucket.<br><br>**Args**:     <ul class="args"><li class="args">`flow (Flow)`: a Prefect Flow to add</li></ul> **Returns**:     <ul class="args"><li class="args">`str`: the key of the newly added flow in the GCS bucket</li></ul> **Raises**:     <ul class="args"><li class="args">`ValueError`: if a flow with the same name is already contained in this storage</li></ul></p>|
 | <div class='method-sig' id='prefect-environments-storage-gcs-gcs-build'><p class="prefect-class">prefect.environments.storage.gcs.GCS.build</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/storage/gcs.py#L151">[source]</a></span></div>
<p class="methods">Build the GCS storage object by uploading Flows to an GCS bucket. This will upload all of the flows found in `storage.flows`.<br><br>**Returns**:     <ul class="args"><li class="args">`Storage`: an GCS object that contains information about how and where         each flow is stored</li></ul></p>|
 | <div class='method-sig' id='prefect-environments-storage-gcs-gcs-get-flow'><p class="prefect-class">prefect.environments.storage.gcs.GCS.get_flow</p>(flow_location=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/storage/gcs.py#L73">[source]</a></span></div>
<p class="methods">Given a flow_location within this Storage object, returns the underlying Flow (if possible).<br><br>**Args**:     <ul class="args"><li class="args">`flow_location (str, optional)`: the location of a flow within this Storage; in this case,         a file path where a Flow has been serialized to. Will use `key` if not provided.</li></ul> **Returns**:     <ul class="args"><li class="args">`Flow`: the requested flow</li></ul> **Raises**:     <ul class="args"><li class="args">`ValueError`: if the flow is not contained in this storage</li></ul></p>|

---
<br>

 ## Azure
 <div class='class-sig' id='prefect-environments-storage-azure-azure'><p class="prefect-sig">class </p><p class="prefect-class">prefect.environments.storage.azure.Azure</p>(container, connection_string=None, blob_name=None, stored_as_script=False, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/storage/azure.py#L16">[source]</a></span></div>

Azure Blob storage class.  This class represents the Storage interface for Flows stored as bytes in an Azure container.

This storage class optionally takes a `blob_name` which will be the name of the Flow object when stored in Azure. If this key is not provided the Flow upload name will take the form `slugified-flow-name/slugified-current-timestamp`.

**Note**: Flows registered with this Storage option will automatically be  labeled with `azure-flow-storage`.

**Args**:     <ul class="args"><li class="args">`container (str)`: the name of the Azure Blob Container to store the Flow     </li><li class="args">`connection_string (str, optional)`: an Azure connection string for communicating with         Blob storage. If not provided the value set in the environment as         `AZURE_STORAGE_CONNECTION_STRING` will be used     </li><li class="args">`blob_name (str, optional)`: a unique key to use for uploading this Flow to Azure. This         is only useful when storing a single Flow using this storage object.     </li><li class="args">`stored_as_script (bool, optional)`: boolean for specifying if the flow has been stored         as a `.py` file. Defaults to `False`     </li><li class="args">`**kwargs (Any, optional)`: any additional `Storage` initialization options</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-environments-storage-azure-azure-add-flow'><p class="prefect-class">prefect.environments.storage.azure.Azure.add_flow</p>(flow)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/storage/azure.py#L102">[source]</a></span></div>
<p class="methods">Method for storing a new flow as bytes in an Azure Blob container.<br><br>**Args**:     <ul class="args"><li class="args">`flow (Flow)`: a Prefect Flow to add</li></ul> **Returns**:     <ul class="args"><li class="args">`str`: the key of the newly added Flow in the container</li></ul> **Raises**:     <ul class="args"><li class="args">`ValueError`: if a flow with the same name is already contained in this storage</li></ul></p>|
 | <div class='method-sig' id='prefect-environments-storage-azure-azure-build'><p class="prefect-class">prefect.environments.storage.azure.Azure.build</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/storage/azure.py#L140">[source]</a></span></div>
<p class="methods">Build the Azure storage object by uploading Flows to an Azure Blob container. This will upload all of the flows found in `storage.flows`.<br><br>**Returns**:     <ul class="args"><li class="args">`Storage`: an Azure object that contains information about how and where         each flow is stored</li></ul></p>|
 | <div class='method-sig' id='prefect-environments-storage-azure-azure-get-flow'><p class="prefect-class">prefect.environments.storage.azure.Azure.get_flow</p>(flow_location=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/storage/azure.py#L67">[source]</a></span></div>
<p class="methods">Given a flow_location within this Storage object, returns the underlying Flow (if possible).<br><br>**Args**:     <ul class="args"><li class="args">`flow_location (str, optional)`: the location of a flow within this Storage; in this case,         a file path where a Flow has been serialized to. Will use `blob_name` if not provided.</li></ul> **Returns**:     <ul class="args"><li class="args">`Flow`: the requested flow</li></ul> **Raises**:     <ul class="args"><li class="args">`ValueError`: if the flow is not contained in this storage</li></ul></p>|

---
<br>

 ## GitHub
 <div class='class-sig' id='prefect-environments-storage-github-github'><p class="prefect-sig">class </p><p class="prefect-class">prefect.environments.storage.github.GitHub</p>(repo, path=None, ref="master", **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/storage/github.py#L11">[source]</a></span></div>

GitHub storage class. This class represents the Storage interface for Flows stored in `.py` files in a GitHub repository.

This class represents a mapping of flow name to file paths contained in the git repo, meaning that all flow files should be pushed independently. A typical workflow using this storage type might look like the following:

- Compose flow `.py` file where flow has GitHub storage:


```python
flow = Flow("my-flow")
flow.storage = GitHub(repo="my/repo", path="/flows/flow.py")

```

- Push this `flow.py` file to the `my/repo` repository under `/flows/flow.py`.

- Call `prefect register -f flow.py` to register this flow with GitHub storage.

**Args**:     <ul class="args"><li class="args">`repo (str)`: the name of a GitHub repository to store this Flow     </li><li class="args">`path (str, optional)`: a path pointing to a flow file in the repo     </li><li class="args">`ref (str, optional)`: a commit SHA-1 value or branch name. Defaults to 'master' if not specified     </li><li class="args">`**kwargs (Any, optional)`: any additional `Storage` initialization options</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-environments-storage-github-github-add-flow'><p class="prefect-class">prefect.environments.storage.github.GitHub.add_flow</p>(flow)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/storage/github.py#L97">[source]</a></span></div>
<p class="methods">Method for storing a new flow as bytes in the local filesytem.<br><br>**Args**:     <ul class="args"><li class="args">`flow (Flow)`: a Prefect Flow to add</li></ul> **Returns**:     <ul class="args"><li class="args">`str`: the location of the added flow in the repo</li></ul> **Raises**:     <ul class="args"><li class="args">`ValueError`: if a flow with the same name is already contained in this storage</li></ul></p>|
 | <div class='method-sig' id='prefect-environments-storage-github-github-build'><p class="prefect-class">prefect.environments.storage.github.GitHub.build</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/storage/github.py#L121">[source]</a></span></div>
<p class="methods">Build the GitHub storage object and run basic healthchecks. Due to this object supporting file based storage no files are committed to the repository during this step. Instead, all files should be committed independently.<br><br>**Returns**:     <ul class="args"><li class="args">`Storage`: a GitHub object that contains information about how and where         each flow is stored</li></ul></p>|
 | <div class='method-sig' id='prefect-environments-storage-github-github-get-flow'><p class="prefect-class">prefect.environments.storage.github.GitHub.get_flow</p>(flow_location=None, ref=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/storage/github.py#L53">[source]</a></span></div>
<p class="methods">Given a flow_location within this Storage object, returns the underlying Flow (if possible). If the Flow is not found an error will be logged and `None` will be returned.<br><br>**Args**:     <ul class="args"><li class="args">`flow_location (str)`: the location of a flow within this Storage; in this case,         a file path on a repository where a Flow file has been committed. Will use `path` if not         provided.     </li><li class="args">`ref (str, optional)`: a commit SHA-1 value or branch name. Defaults to 'master' if not         specified</li></ul> **Returns**:     <ul class="args"><li class="args">`Flow`: the requested Flow</li></ul> **Raises**:     <ul class="args"><li class="args">`ValueError`: if the flow is not contained in this storage     </li><li class="args">`UnknownObjectException`: if the flow file is unable to be retrieved</li></ul></p>|

---
<br>

 ## Webhook
 <div class='class-sig' id='prefect-environments-storage-webhook-webhook'><p class="prefect-sig">class </p><p class="prefect-class">prefect.environments.storage.webhook.Webhook</p>(build_request_kwargs, build_request_http_method, get_flow_request_kwargs, get_flow_request_http_method, stored_as_script=False, flow_script_path=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/storage/webhook.py#L94">[source]</a></span></div>

Webhook storage class. This class represents the Storage interface for Flows stored and retrieved with HTTP requests.

This storage class takes in keyword arguments which describe how to create the requests. These arguments' values can contain template strings which will be filled in dynamically from environment variables or Prefect secrets.

**Note**: Flows registered with this Storage option will automatically be  labeled with `webhook-flow-storage`.

**Args**:     <ul class="args"><li class="args">`build_request_kwargs (dict)`: Dictionary of keyword arguments to the         function from `requests` used to store the flow. Do not supply         `"data"` to this argument, as it will be overwritten with the         flow's content when `.build()` is run.     </li><li class="args">`build_request_http_method (str)`: HTTP method identifying the type of         request to execute when storing the flow. For example, `"POST"` for         `requests.post()`.     </li><li class="args">`get_flow_request_kwargs (dict)`: Dictionary of keyword arguments to         the function from `requests` used to retrieve the flow.     </li><li class="args">`get_flow_request_http_method (str)`: HTTP method identifying the type         of request to execute when storing the flow. For example, `"GET"`         for `requests.post()`.     </li><li class="args">`stored_as_script (bool, optional)`: boolean for specifying if the         flow has been stored as a `.py` file. Defaults to `False`.     </li><li class="args">`flow_script_path (str, optional)`: path to a local `.py` file that         defines the flow. You must pass a value to this argument if         `stored_as_script` is `True`. This script's content will be read         into a string and attached to the request in `build()` as UTF-8         encoded binary data. Similarly, `.get_flow()` expects that the         script's contents will be returned as binary data. This path will         not be sent to Prefect Cloud and is only needed when running         `.build()`.     </li><li class="args">`**kwargs (Any, optional)`: any additional `Storage` initialization         options</li></ul> Including Sensitive Data

------------------------

It is common for requests used with this storage to need access to sensitive information.

For example:

- auth tokens passed in headers like `X-Api-Key` or `Authorization` - auth information passed in to URL as query parameters

`Webhook` storage supports the inclusion of such sensitive information with templating. Any of the string values passed to `build_flow_request_kwargs` or `get_flow_request_kwargs` can include template strings like `${SOME_VARIABLE}`. When `.build()` or `.get_flow()` is run, such values will be replaced with the value of environment variables or, when no matching environment variable is found, Prefect Secrets.

So, for example, to get an API key from an environment variable you can do the following


```python
storage = Webhook(
    build_request_kwargs={
        "url": "some-service/upload",
        "headers" = {
            "Content-Type" = "application/octet-stream",
            "X-Api-Key": "${MY_COOL_ENV_VARIABLE}"
        }
    },
    build_request_http_method="POST",
)

```

You can also take advantage of this templating when only part of a string needs to be replaced.


```python
storage = Webhook(
    get_flow_request_kwargs={
        "url": "some-service/download",
        "headers" = {
            "Accept" = "application/octet-stream",
            "Authorization": "Bearer ${MY_COOL_ENV_VARIABLE}"
        }
    },
    build_request_http_method="POST",
)

```

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-environments-storage-webhook-webhook-add-flow'><p class="prefect-class">prefect.environments.storage.webhook.Webhook.add_flow</p>(flow)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/storage/webhook.py#L269">[source]</a></span></div>
<p class="methods">Method for adding a flow to a `Storage` object's in-memory storage. `.build()` will look here for flows.<br><br>`Webhook` storage only supports a single flow per storage object, so this method will overwrite any existing flows stored in an instance.<br><br>**Args**:     <ul class="args"><li class="args">`flow (Flow)`: a Prefect Flow to add</li></ul> **Returns**:     <ul class="args"><li class="args">`str`: the name of the flow</li></ul></p>|
 | <div class='method-sig' id='prefect-environments-storage-webhook-webhook-build'><p class="prefect-class">prefect.environments.storage.webhook.Webhook.build</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/storage/webhook.py#L288">[source]</a></span></div>
<p class="methods">Build the Webhook storage object by issuing an HTTP request to store the flow.<br><br>If `self.stored_as_script` is `True`, this method will read in the contents of `self.flow_script_path`, convert it to byes, and attach it to the request as `data`.<br><br>The response from this request is stored in `._build_responses`, a dictionary keyed by flow name. If you are using a service where all the details necessary to fetch a flow cannot be known until you've stored it, you can do something like the following.<br><br><br><pre class="language-python"><code class="language-python"><span class="token keyword">import</span> cloudpickle<br><span class="token keyword">import</span> json<br><span class="token keyword">import</span> os<br><span class="token keyword">import</span> random<br><span class="token keyword">import</span> requests<br><br><span class="token keyword">from</span> prefect <span class="token keyword">import</span> task<span class="token punctuation">,</span> Task<span class="token punctuation">,</span> Flow<br><span class="token keyword">from</span> prefect.environments.storage <span class="token keyword">import</span> Webhook<br><br><span class="token decorator">@task</span><br><span class="token keyword">def</span> <span class="token function">random_number</span><span class="token punctuation">(</span><span class="token punctuation">)</span><span class="token punctuation">:</span><br>    <span class="token keyword">return</span> random<span class="token operator">.</span>randint<span class="token punctuation">(</span><span class="token number">0</span><span class="token punctuation">,</span> <span class="token number">100</span><span class="token punctuation">)</span><br><span class="token keyword">with</span> Flow<span class="token punctuation">(</span><span class="token string">"</span><span class="token string">test-flow</span><span class="token string">"</span><span class="token punctuation">)</span> <span class="token keyword">as</span> flow<span class="token punctuation">:</span><br>    random_number<span class="token punctuation">(</span><span class="token punctuation">)</span><br><br><br>flow<span class="token operator">.</span>storage <span class="token operator">=</span> Webhook<span class="token punctuation">(</span><br>    build_request_kwargs<span class="token operator">=</span><span class="token punctuation">{</span><br>        <span class="token string">"</span><span class="token string">url</span><span class="token string">"</span><span class="token punctuation">:</span> <span class="token string">"</span><span class="token string">some-service/upload</span><span class="token string">"</span><span class="token punctuation">,</span><br>        <span class="token string">"</span><span class="token string">headers</span><span class="token string">"</span><span class="token punctuation">:</span> <span class="token punctuation">{</span><span class="token string">"</span><span class="token string">Content-Type</span><span class="token string">"</span><span class="token punctuation">:</span> <span class="token string">"</span><span class="token string">application/octet-stream</span><span class="token string">"</span><span class="token punctuation">}</span><span class="token punctuation">,</span><br>    <span class="token punctuation">}</span><span class="token punctuation">,</span><br>    build_request_http_method<span class="token operator">=</span><span class="token string">"</span><span class="token string">POST</span><span class="token string">"</span><span class="token punctuation">,</span><br>    get_flow_request_kwargs<span class="token operator">=</span><span class="token punctuation">{</span><br>        <span class="token string">"</span><span class="token string">url</span><span class="token string">"</span><span class="token punctuation">:</span> <span class="token string">"</span><span class="token string">some-service/download</span><span class="token string">"</span><span class="token punctuation">,</span><br>        <span class="token string">"</span><span class="token string">headers</span><span class="token string">"</span><span class="token punctuation">:</span> <span class="token punctuation">{</span><span class="token string">"</span><span class="token string">Accept</span><span class="token string">"</span><span class="token punctuation">:</span> <span class="token string">"</span><span class="token string">application/octet-stream</span><span class="token string">"</span><span class="token punctuation">}</span><span class="token punctuation">,</span><br>    <span class="token punctuation">}</span><span class="token punctuation">,</span><br>    get_flow_request_http_method<span class="token operator">=</span><span class="token string">"</span><span class="token string">GET</span><span class="token string">"</span><span class="token punctuation">,</span><br><span class="token punctuation">)</span><br><br>flow<span class="token operator">.</span>storage<span class="token operator">.</span>add_flow<span class="token punctuation">(</span>flow<span class="token punctuation">)</span><br>res <span class="token operator">=</span> flow<span class="token operator">.</span>storage<span class="token operator">.</span>build<span class="token punctuation">(</span><span class="token punctuation">)</span><br><br><span class="token comment"># get the ID from the response</span><br>flow_id <span class="token operator">=</span> res<span class="token operator">.</span>_build_responses<span class="token punctuation">[</span>flow<span class="token operator">.</span>name<span class="token punctuation">]</span><span class="token operator">.</span>json<span class="token punctuation">(</span><span class="token punctuation">)</span><span class="token punctuation">[</span><span class="token string">"</span><span class="token string">id</span><span class="token string">"</span><span class="token punctuation">]</span><br><br><span class="token comment">#  update storage</span><br>flow<span class="token operator">.</span>storage<span class="token operator">.</span>get_flow_request_kwargs<span class="token punctuation">[</span><span class="token string">"</span><span class="token string">url</span><span class="token string">"</span><span class="token punctuation">]</span> <span class="token operator">=</span> <span class="token string">f</span><span class="token string">"</span><span class="token string">{</span>GET_ROUTE<span class="token string">}</span><span class="token string">/</span><span class="token string">{</span>flow_id<span class="token string">}</span><span class="token string">"</span><br></code></pre><br><br><br>**Returns**:     <ul class="args"><li class="args">`Storage`: a Webhook storage object</li></ul> **Raises**:     <ul class="args"><li class="args">requests.exceptions.HTTPError if pushing the flow fails</li></ul></p>|
 | <div class='method-sig' id='prefect-environments-storage-webhook-webhook-get-flow'><p class="prefect-class">prefect.environments.storage.webhook.Webhook.get_flow</p>(flow_location="placeholder")<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/storage/webhook.py#L239">[source]</a></span></div>
<p class="methods">Get the flow from storage. This method will call `cloudpickle.loads()` on the binary content of the flow, so it should only be called in an environment with all of the flow's dependencies.<br><br>**Args**:     <ul class="args"><li class="args">`flow_location (str)`: This argument is included to comply with the         interface used by other storage objects, but it has no meaning         for `Webhook` storage, since `Webhook` only corresponds to a         single flow. Ignore it.</li></ul> **Raises**:     <ul class="args"><li class="args">requests.exceptions.HTTPError if getting the flow fails</li></ul></p>|

---
<br>

 ## GitLab
 <div class='class-sig' id='prefect-environments-storage-gitlab-gitlab'><p class="prefect-sig">class </p><p class="prefect-class">prefect.environments.storage.gitlab.GitLab</p>(repo, host=None, path=None, ref=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/storage/gitlab.py#L11">[source]</a></span></div>

GitLab storage class. This class represents the Storage interface for Flows stored in `.py` files in a GitLab repository.

This class represents a mapping of flow name to file paths contained in the git repo, meaning that all flow files should be pushed independently. A typical workflow using this storage type might look like the following:

- Compose flow `.py` file where flow has GitLab storage:


```python
flow = Flow("my-flow")
# Can also use `repo="123456"`
flow.storage = GitLab(repo="my/repo", path="/flows/flow.py", ref="my-branch")

```

- Push this `flow.py` file to the `my/repo` repository under `/flows/flow.py`.

- Call `prefect register -f flow.py` to register this flow with GitLab storage.

**Args**:     <ul class="args"><li class="args">`repo (str)`: the project path (i.e., 'namespace/project') or ID     </li><li class="args">`host (str, optional)`: If using Gitlab server, the server host. If not specified, defaults         to Gitlab cloud.     </li><li class="args">`path (str, optional)`: a path pointing to a flow file in the repo     </li><li class="args">`ref (str, optional)`: a commit SHA-1 value or branch name     </li><li class="args">`**kwargs (Any, optional)`: any additional `Storage` initialization options</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-environments-storage-gitlab-gitlab-add-flow'><p class="prefect-class">prefect.environments.storage.gitlab.GitLab.add_flow</p>(flow)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/storage/gitlab.py#L111">[source]</a></span></div>
<p class="methods">Method for storing a new flow as bytes in the local filesytem.<br><br>**Args**:     <ul class="args"><li class="args">`flow (Flow)`: a Prefect Flow to add</li></ul> **Returns**:     <ul class="args"><li class="args">`str`: the location of the added flow in the repo</li></ul> **Raises**:     <ul class="args"><li class="args">`ValueError`: if a flow with the same name is already contained in this storage</li></ul></p>|
 | <div class='method-sig' id='prefect-environments-storage-gitlab-gitlab-build'><p class="prefect-class">prefect.environments.storage.gitlab.GitLab.build</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/storage/gitlab.py#L135">[source]</a></span></div>
<p class="methods">Build the GitLab storage object and run basic healthchecks. Due to this object supporting file based storage no files are committed to the repository during this step. Instead, all files should be committed independently.<br><br>**Returns**:     <ul class="args"><li class="args">`Storage`: a GitLab object that contains information about how and where         each flow is stored</li></ul></p>|
 | <div class='method-sig' id='prefect-environments-storage-gitlab-gitlab-get-flow'><p class="prefect-class">prefect.environments.storage.gitlab.GitLab.get_flow</p>(flow_location=None, ref=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/storage/gitlab.py#L62">[source]</a></span></div>
<p class="methods">Given a flow_location within this Storage object, returns the underlying Flow (if possible). If the Flow is not found an error will be logged and `None` will be returned.<br><br>**Args**:     <ul class="args"><li class="args">`flow_location (str)`: the location of a flow within this Storage; in this case,         a file path on a repository where a Flow file has been committed. Will use `path` if not         provided.     </li><li class="args">`ref (str, optional)`: a commit SHA-1 value or branch name. Defaults to 'master' if         not specified</li></ul> **Returns**:     <ul class="args"><li class="args">`Flow`: the requested Flow</li></ul> **Raises**:     <ul class="args"><li class="args">`ValueError`: if the flow is not contained in this storage     </li><li class="args">`UnknownObjectException`: if the flow file is unable to be retrieved</li></ul></p>|

---
<br>

 ## Bitbucket
 <div class='class-sig' id='prefect-environments-storage-bitbucket-bitbucket'><p class="prefect-sig">class </p><p class="prefect-class">prefect.environments.storage.bitbucket.Bitbucket</p>(project, repo, host=None, path=None, ref=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/storage/bitbucket.py#L11">[source]</a></span></div>

Bitbucket storage class. This class represents the Storage interface for Flows stored in `.py` files in a Bitbucket repository.

This class represents a mapping of flow name to file paths contained in the git repo, meaning that all flow files should be pushed independently. A typical workflow using this storage type might look like the following:

- Compose flow `.py` file where flow has Bitbucket storage:


```python
flow = Flow("my-flow")
flow.storage = Bitbucket(project="my.project",repo="my.repo", path="/flows/flow.py", ref="my-branch")

```

- Push this `flow.py` file to the `my.repo` repository under `/flows/flow.py` inside "my.project"     project.

- Call `prefect register -f flow.py` to register this flow with Bitbucket storage.

**Args**:     <ul class="args"><li class="args">`project (str)`: Project that the repository will be in.  Not equivalent to a GitHub project;         required value for all Bitbucket repositories.     </li><li class="args">`repo (str)`: the repository name, with complete taxonomy.     </li><li class="args">`host (str, optional)`: If using Bitbucket server, the server host. If not specified, defaults         to Bitbucket cloud.     </li><li class="args">`path (str, optional)`: a path pointing to a flow file in the repo     </li><li class="args">`ref (str, optional)`: a commit SHA-1 value or branch name     </li><li class="args">`**kwargs (Any, optional)`: any additional `Storage` initialization options</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-environments-storage-bitbucket-bitbucket-add-flow'><p class="prefect-class">prefect.environments.storage.bitbucket.Bitbucket.add_flow</p>(flow)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/storage/bitbucket.py#L119">[source]</a></span></div>
<p class="methods">Method for storing a new flow as bytes in the local filesytem.<br><br>**Args**:     <ul class="args"><li class="args">`flow (Flow)`: a Prefect Flow to add</li></ul> **Returns**:     <ul class="args"><li class="args">`str`: the location of the added flow in the repo</li></ul> **Raises**:     <ul class="args"><li class="args">`ValueError`: if a flow with the same name is already contained in this storage</li></ul></p>|
 | <div class='method-sig' id='prefect-environments-storage-bitbucket-bitbucket-build'><p class="prefect-class">prefect.environments.storage.bitbucket.Bitbucket.build</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/storage/bitbucket.py#L143">[source]</a></span></div>
<p class="methods">Build the Bitbucket storage object and run basic healthchecks. Due to this object supporting file based storage no files are committed to the repository during this step. Instead, all files should be committed independently.<br><br>**Returns**:     <ul class="args"><li class="args">`Storage`: a Bitbucket object that contains information about how and where         each flow is stored</li></ul></p>|
 | <div class='method-sig' id='prefect-environments-storage-bitbucket-bitbucket-get-flow'><p class="prefect-class">prefect.environments.storage.bitbucket.Bitbucket.get_flow</p>(flow_location=None, ref=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/storage/bitbucket.py#L62">[source]</a></span></div>
<p class="methods">Given a flow_location within this Storage object, returns the underlying Flow (if possible). If the Flow is not found an error will be logged and `None` will be returned.<br><br>**Args**:     <ul class="args"><li class="args">`flow_location (str)`: the location of a flow within this Storage; in this case,         a file path on a repository where a Flow file has been committed. Will use `path` if not         provided.     </li><li class="args">`ref (str, optional)`: a commit SHA-1 value or branch name. Defaults to 'master' if         not specified</li></ul> **Returns**:     <ul class="args"><li class="args">`Flow`: the requested Flow; Atlassian API retrieves raw, decoded files.</li></ul> **Raises**:     <ul class="args"><li class="args">`ValueError`: if the flow is not contained in this storage     </li><li class="args">`HTTPError`: if flow is unable to access the Bitbucket repository</li></ul></p>|

---
<br>

 ## CodeCommit
 <div class='class-sig' id='prefect-environments-storage-codecommit-codecommit'><p class="prefect-sig">class </p><p class="prefect-class">prefect.environments.storage.codecommit.CodeCommit</p>(repo, path=None, commit=None, client_options=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/storage/codecommit.py#L10">[source]</a></span></div>

CodeCommit storage class. This class represents the Storage interface for Flows stored in `.py` files in a CodeCommit repository.

This class represents a mapping of flow name to file paths contained in the git repo, meaning that all flow files should be pushed independently. A typical workflow using this storage type might look like the following:

- Compose flow `.py` file where flow has CodeCommit storage:


```python
flow = Flow("my-flow")
flow.storage = CodeCommit(repo="my/repo", path="/flows/flow.py")

```

- Push this `flow.py` file to the `my/repo` repository under `/flows/flow.py`.

- Call `prefect register -f flow.py` to register this flow with CodeCommit storage.

**Args**:     <ul class="args"><li class="args">`repo (str)`: the name of a CodeCommit repository to store this Flow     </li><li class="args">`path (str, optional)`: a path pointing to a flow file in the repo     </li><li class="args">`commit (str, optional)`: fully quaified reference that identifies the commit       that contains the file. For example, you can specify a full commit ID, a tag,       a branch name, or a reference such as refs/heads/master. If none is provided,       the head commit is used     </li><li class="args">`client_options (dict, optional)`: Additional options for the `boto3` client.     </li><li class="args">`**kwargs (Any, optional)`: any additional `Storage` initialization options</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-environments-storage-codecommit-codecommit-add-flow'><p class="prefect-class">prefect.environments.storage.codecommit.CodeCommit.add_flow</p>(flow)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/storage/codecommit.py#L102">[source]</a></span></div>
<p class="methods">Method for storing a new flow as bytes in the local filesytem.<br><br>**Args**:     <ul class="args"><li class="args">`flow (Flow)`: a Prefect Flow to add</li></ul> **Returns**:     <ul class="args"><li class="args">`str`: the location of the added flow in the repo</li></ul> **Raises**:     <ul class="args"><li class="args">`ValueError`: if a flow with the same name is already contained in this storage</li></ul></p>|
 | <div class='method-sig' id='prefect-environments-storage-codecommit-codecommit-build'><p class="prefect-class">prefect.environments.storage.codecommit.CodeCommit.build</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/storage/codecommit.py#L126">[source]</a></span></div>
<p class="methods">Build the CodeCommit storage object and run basic healthchecks. Due to this object supporting file based storage no files are committed to the repository during this step. Instead, all files should be committed independently.<br><br>**Returns**:     <ul class="args"><li class="args">`Storage`: a CodeCommit object that contains information about how and where         each flow is stored</li></ul></p>|
 | <div class='method-sig' id='prefect-environments-storage-codecommit-codecommit-get-flow'><p class="prefect-class">prefect.environments.storage.codecommit.CodeCommit.get_flow</p>(flow_location=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/storage/codecommit.py#L58">[source]</a></span></div>
<p class="methods">Given a flow_location within this Storage object, returns the underlying Flow (if possible). If the Flow is not found an error will be logged and `None` will be returned.<br><br>**Args**:     <ul class="args"><li class="args">`flow_location (str)`: the location of a flow within this Storage; in this case,         a file path on a repository where a Flow file has been committed. Will use `path` if not         provided.</li></ul> **Returns**:     <ul class="args"><li class="args">`Flow`: the requested Flow</li></ul> **Raises**:     <ul class="args"><li class="args">`ValueError`: if the flow is not contained in this storage     </li><li class="args">`UnknownObjectException`: if the flow file is unable to be retrieved</li></ul></p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on December 16, 2020 at 21:36 UTC</p>