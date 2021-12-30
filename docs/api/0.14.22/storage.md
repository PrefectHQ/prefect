---
sidebarDepth: 2
editLink: false
---
# Storage
---
The Prefect Storage interface encapsulates logic for storing flows. Each
storage unit is able to store _multiple_ flows (with the constraint of name
uniqueness within a given unit).
 ## Storage
 <div class='class-sig' id='prefect-storage-base-storage'><p class="prefect-sig">class </p><p class="prefect-class">prefect.storage.base.Storage</p>(result=None, secrets=None, labels=None, add_default_labels=None, stored_as_script=False)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/storage/base.py#L15">[source]</a></span></div>

Base interface for Storage objects. All kwargs present in this base class are valid on storage subclasses.

**Args**:     <ul class="args"><li class="args">`result (Result, optional)`: a default result to use for         all flows which utilize this storage class     </li><li class="args">`secrets (List[str], optional)`: a list of Prefect Secrets which will be used to         populate `prefect.context` for each flow run.  Used primarily for providing         authentication credentials.     </li><li class="args">`labels (List[str], optional)`: a list of labels to associate with this `Storage`.     </li><li class="args">`add_default_labels (bool)`: If `True`, adds the storage specific default label (if         applicable) to the storage labels. Defaults to the value specified in the         configuration at `flows.defaults.storage.add_default_labels`.     </li><li class="args">`stored_as_script (bool, optional)`: boolean for specifying if the flow has been stored         as a `.py` file. Defaults to `False`</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-storage-base-storage-add-flow'><p class="prefect-class">prefect.storage.base.Storage.add_flow</p>(flow)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/storage/base.py#L91">[source]</a></span></div>
<p class="methods">Method for adding a new flow to this Storage object.<br><br>**Args**:     <ul class="args"><li class="args">`flow (Flow)`: a Prefect Flow to add</li></ul> **Returns**:     <ul class="args"><li class="args">`str`: the location of the newly added flow in this Storage object</li></ul></p>|
 | <div class='method-sig' id='prefect-storage-base-storage-build'><p class="prefect-class">prefect.storage.base.Storage.build</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/storage/base.py#L125">[source]</a></span></div>
<p class="methods">Build the Storage object.<br><br>**Returns**:     <ul class="args"><li class="args">`Storage`: a Storage object that contains information about how and where         each flow is stored</li></ul></p>|

---
<br>

 ## Azure
 <div class='class-sig' id='prefect-storage-azure-azure'><p class="prefect-sig">class </p><p class="prefect-class">prefect.storage.azure.Azure</p>(container, connection_string=None, blob_name=None, stored_as_script=False, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/storage/azure.py#L19">[source]</a></span></div>

Azure Blob storage class.  This class represents the Storage interface for Flows stored as bytes in an Azure container.

This storage class optionally takes a `blob_name` which will be the name of the Flow object when stored in Azure. If this key is not provided the Flow upload name will take the form `slugified-flow-name/slugified-current-timestamp`.

**Args**:     <ul class="args"><li class="args">`container (str)`: the name of the Azure Blob Container to store the Flow     </li><li class="args">`connection_string (str, optional)`: an Azure connection string for communicating with         Blob storage. If not provided the value set in the environment as         `AZURE_STORAGE_CONNECTION_STRING` will be used     </li><li class="args">`blob_name (str, optional)`: a unique key to use for uploading this Flow to Azure. This         is only useful when storing a single Flow using this storage object.     </li><li class="args">`stored_as_script (bool, optional)`: boolean for specifying if the flow has been stored         as a `.py` file. Defaults to `False`     </li><li class="args">`**kwargs (Any, optional)`: any additional `Storage` initialization options</li></ul>


---
<br>

 ## Bitbucket
 <div class='class-sig' id='prefect-storage-bitbucket-bitbucket'><p class="prefect-sig">class </p><p class="prefect-class">prefect.storage.bitbucket.Bitbucket</p>(project, repo, workspace=None, host=None, path=None, ref=None, access_token_secret=None, cloud_username_secret=None, cloud_app_password_secret=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/storage/bitbucket.py#L29">[source]</a></span></div>

Bitbucket storage class. This class represents the Storage interface for Flows stored in `.py` files in a Bitbucket repository. This is for Bitbucket Server or Bitbucket Cloud.

This class represents a mapping of flow name to file paths contained in the git repo, meaning that all flow files should be pushed independently. A typical workflow using this storage type might look like the following:

- Compose flow `.py` file where flow has Bitbucket storage:


```python
flow = Flow("my-flow")
flow.storage = Bitbucket(
    project="my.project", repo="my.repo", path="flows/flow.py", ref="my-branch"
)

```

- Push this `flow.py` file to the `my.repo` repository under `flows/flow.py` inside "my.project"     project.

- Call `prefect register -f flow.py` to register this flow with Bitbucket storage.

**Args**:     <ul class="args"><li class="args">`project (str)`: project that the repository will be in.  Not equivalent to a GitHub project;         required value for all Bitbucket repositories.     </li><li class="args">`repo (str)`: the repository name, with complete taxonomy.     </li><li class="args">`workspace (str, optional)`: the workspace name. Bitbucket cloud only.     </li><li class="args">`host (str, optional)`: the server host. Bitbucket server only.     </li><li class="args">`path (str, optional)`: a path pointing to a flow file in the repo     </li><li class="args">`ref (str, optional)`: a commit SHA-1 value or branch name or tag. If not specified,         defaults to master branch for the repo.     </li><li class="args">`access_token_secret (str, optional)`: the name of a Prefect secret         that contains a Bitbucket access token to use when loading flows from         this storage. Bitbucket Server only     </li><li class="args">`cloud_username_secret (str, optional)`: the name of a Prefect secret that contains a         Bitbucket username to use when loading flows from this storage. Bitbucket Cloud only.     </li><li class="args">`cloud_app_password_secret (str, optional)`: the name of a Prefect secret that contains a         Bitbucket app password, from the account associated with the `cloud_username_secret`,         to use when loading flows from this storage. Bitbucket Cloud only.     </li><li class="args">`**kwargs (Any, optional)`: any additional `Storage` initialization options</li></ul>


---
<br>

 ## CodeCommit
 <div class='class-sig' id='prefect-storage-codecommit-codecommit'><p class="prefect-sig">class </p><p class="prefect-class">prefect.storage.codecommit.CodeCommit</p>(repo, path=None, commit=None, client_options=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/storage/codecommit.py#L10">[source]</a></span></div>

CodeCommit storage class. This class represents the Storage interface for Flows stored in `.py` files in a CodeCommit repository.

This class represents a mapping of flow name to file paths contained in the git repo, meaning that all flow files should be pushed independently. A typical workflow using this storage type might look like the following:

- Compose flow `.py` file where flow has CodeCommit storage:


```python
flow = Flow("my-flow")
flow.storage = CodeCommit(repo="my/repo", path="flows/flow.py")

```

- Push this `flow.py` file to the `my/repo` repository under `flows/flow.py`.

- Call `prefect register -f flow.py` to register this flow with CodeCommit storage.

**Args**:     <ul class="args"><li class="args">`repo (str)`: the name of a CodeCommit repository to store this Flow     </li><li class="args">`path (str, optional)`: a path pointing to a flow file in the repo     </li><li class="args">`commit (str, optional)`: fully quaified reference that identifies the commit       that contains the file. For example, you can specify a full commit ID, a tag,       a branch name, or a reference such as refs/heads/master. If none is provided,       the head commit is used     </li><li class="args">`client_options (dict, optional)`: Additional options for the `boto3` client.     </li><li class="args">`**kwargs (Any, optional)`: any additional `Storage` initialization options</li></ul>


---
<br>

 ## Docker
 <div class='class-sig' id='prefect-storage-docker-docker'><p class="prefect-sig">class </p><p class="prefect-class">prefect.storage.docker.Docker</p>(registry_url=None, base_image=None, dockerfile=None, python_dependencies=None, image_name=None, image_tag=None, env_vars=None, files=None, prefect_version=None, local_image=False, ignore_healthchecks=False, base_url=None, tls_config=False, build_kwargs=None, prefect_directory=&quot;/opt/prefect&quot;, path=None, stored_as_script=False, extra_dockerfile_commands=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/storage/docker.py#L37">[source]</a></span></div>

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

**Args**:     <ul class="args"><li class="args">`registry_url (str, optional)`: URL of a registry to push the image to;         image will not be pushed if not provided     </li><li class="args">`base_image (str, optional)`: the base image for this when building this         image (e.g. `python:3.6`), defaults to the `prefecthq/prefect` image         matching your python version and prefect core library version used         at runtime.     </li><li class="args">`dockerfile (str, optional)`: a path to a Dockerfile to use in building         this storage; note that, if provided, your present working directory         will be used as the build context     </li><li class="args">`python_dependencies (List[str], optional)`: list of pip installable         dependencies for the image     </li><li class="args">`image_name (str, optional)`: name of the image to use when building,         populated with a UUID after build     </li><li class="args">`image_tag (str, optional)`: tag of the image to use when building,         populated with a UUID after build     </li><li class="args">`env_vars (dict, optional)`: a dictionary of environment variables to         use when building     </li><li class="args">`files (dict, optional)`: a dictionary of files or directories to copy into         the image when building. Takes the format of `{'src': 'dest'}`     </li><li class="args">`prefect_version (str, optional)`: an optional branch, tag, or commit         specifying the version of prefect you want installed into the container;         defaults to the version you are currently using or `"master"` if your         version is ahead of the latest tag     </li><li class="args">`local_image (bool, optional)`: an optional flag whether or not to use a         local docker image, if True then a pull will not be attempted     </li><li class="args">`ignore_healthchecks (bool, optional)`: if True, the Docker healthchecks         are not added to the Dockerfile. If False (default), healthchecks         are included.     </li><li class="args">`base_url (str, optional)`: a URL of a Docker daemon to use when for         Docker related functionality.  Defaults to DOCKER_HOST env var if not set     </li><li class="args">`tls_config (Union[bool, docker.tls.TLSConfig], optional)`: a TLS configuration to pass         to the Docker client.         [Documentation](https://docker-py.readthedocs.io/en/stable/tls.html#docker.tls.TLSConfig)     </li><li class="args">`build_kwargs (dict, optional)`: Additional keyword arguments to pass to Docker's build         step. [Documentation](https://docker-py.readthedocs.io/en/stable/         api.html#docker.api.build.BuildApiMixin.build)     </li><li class="args">`prefect_directory (str, optional)`: Path to the directory where prefect configuration/flows          should be stored inside the Docker image. Defaults to `/opt/prefect`.     </li><li class="args">`path (str, optional)`: a direct path to the location of the flow file in the Docker image         if `stored_as_script=True`.     </li><li class="args">`stored_as_script (bool, optional)`: boolean for specifying if the flow has been stored         as a `.py` file. Defaults to `False`     </li><li class="args">`extra_dockerfile_commands (list[str], optional)`: list of Docker build commands         which are injected at the end of generated DockerFile (before the health checks).         Defaults to `None`     </li><li class="args">`**kwargs (Any, optional)`: any additional `Storage` initialization options</li></ul> **Raises**:     <ul class="args"><li class="args">`ValueError`: if both `base_image` and `dockerfile` are provided</li></ul>


---
<br>

 ## GCS
 <div class='class-sig' id='prefect-storage-gcs-gcs'><p class="prefect-sig">class </p><p class="prefect-class">prefect.storage.gcs.GCS</p>(bucket, key=None, project=None, stored_as_script=False, local_script_path=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/storage/gcs.py#L20">[source]</a></span></div>

GoogleCloudStorage storage class.  This class represents the Storage interface for Flows stored as bytes in an GCS bucket.  To authenticate with Google Cloud, you need to ensure that your Prefect Agent has the proper credentials available (see https://cloud.google.com/docs/authentication/production for all the authentication options).

This storage class optionally takes a `key` which will be the name of the Flow object when stored in GCS. If this key is not provided the Flow upload name will take the form `slugified-flow-name/slugified-current-timestamp`.

**Args**:     <ul class="args"><li class="args">`bucket (str, optional)`: the name of the GCS Bucket to store the Flow     </li><li class="args">`key (str, optional)`: a unique key to use for uploading this Flow to GCS. This         is only useful when storing a single Flow using this storage object.     </li><li class="args">`project (str, optional)`: the google project where any GCS API requests are billed to;         if not provided, the project will be inferred from your Google Cloud credentials.     </li><li class="args">`stored_as_script (bool, optional)`: boolean for specifying if the flow has been stored         as a `.py` file. Defaults to `False`     </li><li class="args">`local_script_path (str, optional)`: the path to a local script to upload when `stored_as_script`         is set to `True`. If not set then the value of `local_script_path` from `prefect.context` is         used. If neither are set then script will not be uploaded and users should manually place the         script file in the desired `key` location in a GCS bucket.     </li><li class="args">`**kwargs (Any, optional)`: any additional `Storage` initialization options</li></ul>


---
<br>

 ## Git
 <div class='class-sig' id='prefect-storage-git-git'><p class="prefect-sig">class </p><p class="prefect-class">prefect.storage.git.Git</p>(flow_path, repo, repo_host=&quot;github.com&quot;, flow_name=None, git_token_secret_name=None, git_token_username=None, branch_name=None, tag=None, commit=None, clone_depth=1, use_ssh=False, format_access_token=True, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/storage/git.py#L14">[source]</a></span></div>

Git storage class. This class represents the Storage interface for Flows stored in `.py` files in a git repository.

This class represents a mapping of flow name to file paths contained in the git repo, meaning that all flow files should be pushed independently.

A typical workflow using this storage type might look like the following:

- Compose flow `.py` file where flow has Git storage:


```python
flow = Flow("my-flow")
flow.storage = Git(repo="my/repo", flow_path="flows/flow.py", repo_host="github.com")

```

- Push this `flow.py` file to the `my/repo` repository under `flows/flow.py`.

- Call `prefect register -f flow.py` to register this flow with Git storage.

**Args**:     <ul class="args"><li class="args">`flow_path (str)`: A file path pointing to a .py file containing a flow     </li><li class="args">`repo (str)`: the name of a git repository to store this Flow     </li><li class="args">`repo_host (str, optional)`: The site hosting the repo. Defaults to 'github.com'     </li><li class="args">`flow_name (str, optional)`: A specific name of a flow to extract from a file.         If not set then the first flow object retrieved from file will be returned.     </li><li class="args">`git_token_secret_name (str, optional)`: The name of the Prefect Secret containing         an access token for the repo. Defaults to None     </li><li class="args">`git_token_username (str, optional)`: the username associated with git access token,         if not provided it will default to repo owner     </li><li class="args">`branch_name (str, optional)`: branch name, if not specified and `tag` and `commit_sha`         not specified, repo default branch latest commit will be used     </li><li class="args">`tag (str, optional)`: tag name, if not specified and `branch_name` and `commit_sha`         not specified, repo default branch latest commit will be used     </li><li class="args">`commit (str, optional)`: a commit SHA-1 value, if not specified and `branch_name`         and `tag` not specified, repo default branch latest commit will be used     </li><li class="args">`clone_depth (int)`: the number of history revisions in cloning, defaults to 1     </li><li class="args">`use_ssh (bool)`: if True, cloning will use ssh. Ssh keys must be correctly         configured in the environment for this to work     </li><li class="args">`format_access_token (bool)`: if True, the class will attempt to format access tokens         for common git hosting sites     </li><li class="args">`**kwargs (Any, optional)`: any additional `Storage` initialization options</li></ul>


---
<br>

 ## GitHub
 <div class='class-sig' id='prefect-storage-github-github'><p class="prefect-sig">class </p><p class="prefect-class">prefect.storage.github.GitHub</p>(repo, path, ref=None, access_token_secret=None, base_url=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/storage/github.py#L14">[source]</a></span></div>

GitHub storage class. This class represents the Storage interface for Flows stored in `.py` files in a GitHub repository.

This class represents a mapping of flow name to file paths contained in the git repo, meaning that all flow files should be pushed independently. A typical workflow using this storage type might look like the following:

- Compose flow `.py` file where flow has GitHub storage:


```python
flow = Flow("my-flow")
flow.storage = GitHub(repo="my/repo", path="flows/flow.py")

```

- Push this `flow.py` file to the `my/repo` repository under `flows/flow.py`.

- Call `prefect register -f flow.py` to register this flow with GitHub storage.

**Args**:     <ul class="args"><li class="args">`repo (str)`: the name of a GitHub repository to store this Flow     </li><li class="args">`path (str)`: a path pointing to a flow file in the repo     </li><li class="args">`ref (str, optional)`: a commit SHA-1 value, tag, or branch name. If not specified,         defaults to the default branch for the repo.     </li><li class="args">`access_token_secret (str, optional)`: The name of a Prefect secret         that contains a GitHub access token to use when loading flows from         this storage.     </li><li class="args">`base_url(str, optional)`: the Github REST api url for the repo. If not specified,         https://api.github.com is used.     </li><li class="args">`**kwargs (Any, optional)`: any additional `Storage` initialization options</li></ul>


---
<br>

 ## GitLab
 <div class='class-sig' id='prefect-storage-gitlab-gitlab'><p class="prefect-sig">class </p><p class="prefect-class">prefect.storage.gitlab.GitLab</p>(repo, host=None, path=None, ref=None, access_token_secret=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/storage/gitlab.py#L15">[source]</a></span></div>

GitLab storage class. This class represents the Storage interface for Flows stored in `.py` files in a GitLab repository.

This class represents a mapping of flow name to file paths contained in the git repo, meaning that all flow files should be pushed independently. A typical workflow using this storage type might look like the following:

- Compose flow `.py` file where flow has GitLab storage:


```python
flow = Flow("my-flow")
# Can also use `repo="123456"`
flow.storage = GitLab(repo="my/repo", path="flows/flow.py", ref="my-branch")

```

- Push this `flow.py` file to the `my/repo` repository under `flows/flow.py`.

- Call `prefect register flow -f flow.py --project 'my-prefect-project'` to register this flow with GitLab storage.

**Args**:     <ul class="args"><li class="args">`repo (str)`: the project path (i.e., 'namespace/project') or ID     </li><li class="args">`host (str, optional)`: If using GitLab server, the server host. If not         specified, defaults to Gitlab cloud.     </li><li class="args">`path (str, optional)`: a path pointing to a flow file in the repo     </li><li class="args">`ref (str, optional)`: a commit SHA-1 value or branch name     </li><li class="args">`access_token_secret (str, optional)`: The name of a Prefect secret         that contains a GitLab access token to use when loading flows from         this storage.     </li><li class="args">`**kwargs (Any, optional)`: any additional `Storage` initialization options</li></ul>


---
<br>

 ## Local
 <div class='class-sig' id='prefect-storage-local-local'><p class="prefect-sig">class </p><p class="prefect-class">prefect.storage.local.Local</p>(directory=None, validate=True, path=None, stored_as_script=False, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/storage/local.py#L22">[source]</a></span></div>

Local storage class.  This class represents the Storage interface for Flows stored as bytes in the local filesystem.

Note that if you register a Flow with Prefect Cloud using this storage, your flow will automatically be labeled with your machine's hostname. This ensures that only agents that are known to be running on the same filesystem can run your flow.

**Args**:     <ul class="args"><li class="args">`directory (str, optional)`: the directory the flows will be stored in;         defaults to `~/.prefect/flows`.  If it doesn't already exist, it will be         created for you.     </li><li class="args">`validate (bool, optional)`: a boolean specifying whether to validate the         provided directory path; if `True`, the directory will be converted to an         absolute path and created.  Defaults to `True`     </li><li class="args">`path (str, optional)`: a direct path to the location of the flow file if         `stored_as_script=True`, otherwise this path will be used when storing the serialized,         pickled flow. If `stored_as_script=True`, the direct path may be a file path         (such as 'path/to/myflow.py') or a direct python path (such as 'myrepo.mymodule.myflow')     </li><li class="args">`stored_as_script (bool, optional)`: boolean for specifying if the flow has been stored         as a `.py` file. Defaults to `False`     </li><li class="args">`**kwargs (Any, optional)`: any additional `Storage` initialization options</li></ul>


---
<br>

 ## Module
 <div class='class-sig' id='prefect-storage-module-module'><p class="prefect-sig">class </p><p class="prefect-class">prefect.storage.module.Module</p>(module, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/storage/module.py#L10">[source]</a></span></div>

A Prefect Storage class for referencing flows that can be imported from a python module.

**Args**:     <ul class="args"><li class="args">`module (str)`: The module to import the flow from.     </li><li class="args">`**kwargs (Any, optional)`: any additional `Storage` options.</li></ul> **Example**:

Suppose you have a python module `myproject.flows` that contains all your Prefect flows. If this module is installed and available in your execution environment you can use `Module` storage to reference and load the flows.


```python
from prefect import Flow
from prefect.storage import Module

flow = Flow("module storage example")
flow.storage = Module("myproject.flows")

# Tip: you can use `__name__` to automatically reference the current module
flow.storage = Module(__name__)

```


---
<br>

 ## S3
 <div class='class-sig' id='prefect-storage-s3-s3'><p class="prefect-sig">class </p><p class="prefect-class">prefect.storage.s3.S3</p>(bucket, key=None, stored_as_script=False, local_script_path=None, client_options=None, upload_options=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/storage/s3.py#L21">[source]</a></span></div>

S3 storage class.  This class represents the Storage interface for Flows stored as bytes in an S3 bucket.

This storage class optionally takes a `key` which will be the name of the Flow object when stored in S3. If this key is not provided the Flow upload name will take the form `slugified-flow-name/slugified-current-timestamp`.

**Args**:     <ul class="args"><li class="args">`bucket (str)`: the name of the S3 Bucket to store Flows     </li><li class="args">`key (str, optional)`: a unique key to use for uploading a Flow to S3. This         is only useful when storing a single Flow using this storage object.     </li><li class="args">`stored_as_script (bool, optional)`: boolean for specifying if the flow has been stored         as a `.py` file. Defaults to `False`     </li><li class="args">`local_script_path (str, optional)`: the path to a local script to upload when `stored_as_script`         is set to `True`. If not set then the value of `local_script_path` from `prefect.context` is         used. If neither are set then script will not be uploaded and users should manually place the         script file in the desired `key` location in an S3 bucket.     </li><li class="args">`client_options (dict, optional)`: Additional options for the `boto3` client.     </li><li class="args">`upload_options (dict, optional)`: Additional options s3 client upload_file()         and upload_fileobj() functions 'ExtraArgs' argument.     </li><li class="args">`**kwargs (Any, optional)`: any additional `Storage` initialization options</li></ul>


---
<br>

 ## Webhook
 <div class='class-sig' id='prefect-storage-webhook-webhook'><p class="prefect-sig">class </p><p class="prefect-class">prefect.storage.webhook.Webhook</p>(build_request_kwargs, build_request_http_method, get_flow_request_kwargs, get_flow_request_http_method, stored_as_script=False, flow_script_path=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/storage/webhook.py#L97">[source]</a></span></div>

Webhook storage class. This class represents the Storage interface for Flows stored and retrieved with HTTP requests.

This storage class takes in keyword arguments which describe how to create the requests. These arguments' values can contain template strings which will be filled in dynamically from environment variables or Prefect secrets.

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


---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on July 1, 2021 at 18:35 UTC</p>