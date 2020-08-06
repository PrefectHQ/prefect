---
sidebarDepth: 2
editLink: false
---
# Result Subclasses
---
`Result` subclasses are the backbone of tracking the value, type and optional persistence method of return values from tasks by exposing a `read` / `write` / `exists` interface for common storage backends. Results can also be instantiated directly by the user in a task to use those methods to interact with persistent storage and track data besides a task's return value.

A results `read` / `write` / `exists` methods depends on a result's `location` attribute, which can be a concrete string or a templated string that will be formatted at time of `write` using `prefect.context`.

Note that a result's `read` and `write` methods return new `Result` instances, the former with their `location` attribute formatted, and the latter with the `value` attribute hydrated.

For example, here is how you would use a result in a task directly to read and write arbitrary pieces of data:

```python
import prefect
from prefect import task
from prefect.engine.results import S3Result

MY_RESULTS = S3Result(bucket='my_bucket', location="{task_name}.txt")

@task(name="my_example_task")
def my_example_task():
    # read data from a file in the bucket.
    my_task_data = MY_RESULTS.read(location="some_data_in_my_bucket.csv")
    print(my_task_data.value) # is the deserialized data that was in the file s3://my_bucket/some_data_in_my_bucket.csv
    
    # write data to the templated location in the bucket using prefect context
    data = 3
    my_task_data = MY_RESULTS.write(data, **prefect.context)
    print(my_task_data.value) # is the value `3
    print(my_task_data.location) # is "my_example_task.txt"

```

Results will only persist return data if checkpointing is turned on. To learn more about how to use results and how to configure checkpointing, read our tutorial on [Using Results](/core/advanced_tutorials/using-results.md).
 ## PrefectResult
 <div class='class-sig' id='prefect-engine-results-prefect-result-prefectresult'><p class="prefect-sig">class </p><p class="prefect-class">prefect.engine.results.prefect_result.PrefectResult</p>(**kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/results/prefect_result.py#L7">[source]</a></span></div>

Hook for storing and retrieving JSON serializable Python objects that can safely be stored directly in a Prefect database.

**Args**:     <ul class="args"><li class="args">`**kwargs (Any, optional)`: any additional `Result` initialization options</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-engine-results-prefect-result-prefectresult-exists'><p class="prefect-class">prefect.engine.results.prefect_result.PrefectResult.exists</p>(location, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/results/prefect_result.py#L63">[source]</a></span></div>
<p class="methods">Confirms that the provided value is JSON deserializable.<br><br>**Args**:     <ul class="args"><li class="args">`location (str)`: the value to test     </li><li class="args">`**kwargs (Any)`: unused, for compatibility with the interface</li></ul>**Returns**:     <ul class="args"><li class="args">`bool`: whether the provided string can be deserialized</li></ul></p>|
 | <div class='method-sig' id='prefect-engine-results-prefect-result-prefectresult-read'><p class="prefect-class">prefect.engine.results.prefect_result.PrefectResult.read</p>(location)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/results/prefect_result.py#L31">[source]</a></span></div>
<p class="methods">Returns the underlying value regardless of the argument passed.<br><br>**Args**:     <ul class="args"><li class="args">`location (str)`: an unused argument</li></ul>**Returns**:     <ul class="args"><li class="args">`Result`: a new result instance with the data represented by the location</li></ul></p>|
 | <div class='method-sig' id='prefect-engine-results-prefect-result-prefectresult-write'><p class="prefect-class">prefect.engine.results.prefect_result.PrefectResult.write</p>(value, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/results/prefect_result.py#L46">[source]</a></span></div>
<p class="methods">JSON serializes `self.value` and returns `self`.<br><br>**Args**:     <ul class="args"><li class="args">`value (Any)`: the value to write; will then be stored as the `value` attribute         of the returned `Result` instance     </li><li class="args">`**kwargs (optional)`: unused, for compatibility with the interface</li></ul>**Returns**:     <ul class="args"><li class="args">`Result`: returns a new `Result` with both `value` and `location` attributes</li></ul></p>|

---
<br>

 ## GCSResult
 <div class='class-sig' id='prefect-engine-results-gcs-result-gcsresult'><p class="prefect-sig">class </p><p class="prefect-class">prefect.engine.results.gcs_result.GCSResult</p>(bucket=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/results/gcs_result.py#L9">[source]</a></span></div>

Result that is written to and read from a Google Cloud Bucket.

To authenticate with Google Cloud, you need to ensure that your flow's runtime environment has the proper credentials available (see https://cloud.google.com/docs/authentication/production for all the authentication options).

You can also optionally provide your service account key to `prefect.context.secrets.GCP_CREDENTIALS` for automatic authentication - see [Third Party Authentication](../../../orchestration/recipes/third_party_auth.html) for more information.

To read more about service account keys see https://cloud.google.com/iam/docs/creating-managing-service-account-keys.  To read more about the JSON representation of service account keys see https://cloud.google.com/iam/docs/reference/rest/v1/projects.serviceAccounts.keys.

**Args**:     <ul class="args"><li class="args">`bucket (str)`: the name of the bucket to write to / read from     </li><li class="args">`**kwargs (Any, optional)`: any additional `Result` initialization options</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-engine-results-gcs-result-gcsresult-exists'><p class="prefect-class">prefect.engine.results.gcs_result.GCSResult.exists</p>(location, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/results/gcs_result.py#L112">[source]</a></span></div>
<p class="methods">Checks whether the target result exists.<br><br>Does not validate whether the result is `valid`, only that it is present.<br><br>**Args**:     <ul class="args"><li class="args">`location (str)`: Location of the result in the specific result target.         Will check whether the provided location exists     </li><li class="args">`**kwargs (Any)`: string format arguments for `location`</li></ul>**Returns**:     <ul class="args"><li class="args">`bool`: whether or not the target result exists.</li></ul></p>|
 | <div class='method-sig' id='prefect-engine-results-gcs-result-gcsresult-read'><p class="prefect-class">prefect.engine.results.gcs_result.GCSResult.read</p>(location)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/results/gcs_result.py#L82">[source]</a></span></div>
<p class="methods">Reads a result from a GCS bucket and returns a corresponding `Result` instance.<br><br>**Args**:     <ul class="args"><li class="args">`location (str)`: the GCS URI to read from</li></ul>**Returns**:     <ul class="args"><li class="args">`Result`: the read result</li></ul></p>|
 | <div class='method-sig' id='prefect-engine-results-gcs-result-gcsresult-write'><p class="prefect-class">prefect.engine.results.gcs_result.GCSResult.write</p>(value, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/results/gcs_result.py#L58">[source]</a></span></div>
<p class="methods">Writes the result value to a location in GCS and returns the resulting URI.<br><br>**Args**:     <ul class="args"><li class="args">`value (Any)`: the value to write; will then be stored as the `value` attribute         of the returned `Result` instance     </li><li class="args">`**kwargs (optional)`: if provided, will be used to format the location template         to determine the location to write to</li></ul>**Returns**:     <ul class="args"><li class="args">`Result`: a new Result instance with the appropriately formatted location</li></ul></p>|

---
<br>

 ## LocalResult
 <div class='class-sig' id='prefect-engine-results-local-result-localresult'><p class="prefect-sig">class </p><p class="prefect-class">prefect.engine.results.local_result.LocalResult</p>(dir=None, validate_dir=True, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/results/local_result.py#L11">[source]</a></span></div>

Result that is written to and retrieved from the local file system.

**Note**: If this result raises a `PermissionError` that could mean it is attempting to write results to a directory that it is not permissioned for. In that case it may be helpful to specify a specific `dir` for that result instance.

**Args**:     <ul class="args"><li class="args">`dir (str, optional)`: the _absolute_ path to a directory for storing         all results; defaults to `${prefect.config.home_dir}/results`     </li><li class="args">`validate_dir (bool, optional)`: a boolean specifying whether to validate the         provided directory path; if `True`, the directory will be converted to an         absolute path and created.  Defaults to `True`     </li><li class="args">`**kwargs (Any, optional)`: any additional `Result` initialization options</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-engine-results-local-result-localresult-exists'><p class="prefect-class">prefect.engine.results.local_result.LocalResult.exists</p>(location, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/results/local_result.py#L120">[source]</a></span></div>
<p class="methods">Checks whether the target result exists in the file system.<br><br>Does not validate whether the result is `valid`, only that it is present.<br><br>**Args**:     <ul class="args"><li class="args">`location (str)`: Location of the result in the specific result target.         Will check whether the provided location exists     </li><li class="args">`**kwargs (Any)`: string format arguments for `location`</li></ul>**Returns**:     <ul class="args"><li class="args">`bool`: whether or not the target result exists</li></ul></p>|
 | <div class='method-sig' id='prefect-engine-results-local-result-localresult-read'><p class="prefect-class">prefect.engine.results.local_result.LocalResult.read</p>(location)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/results/local_result.py#L63">[source]</a></span></div>
<p class="methods">Reads a result from the local file system and returns the corresponding `Result` instance.<br><br>**Args**:     <ul class="args"><li class="args">`location (str)`: the location to read from</li></ul>**Returns**:     <ul class="args"><li class="args">`Result`: a new result instance with the data represented by the location</li></ul></p>|
 | <div class='method-sig' id='prefect-engine-results-local-result-localresult-write'><p class="prefect-class">prefect.engine.results.local_result.LocalResult.write</p>(value, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/results/local_result.py#L87">[source]</a></span></div>
<p class="methods">Writes the result to a location in the local file system and returns a new `Result` object with the result's location.<br><br>**Args**:     <ul class="args"><li class="args">`value (Any)`: the value to write; will then be stored as the `value` attribute         of the returned `Result` instance     </li><li class="args">`**kwargs (optional)`: if provided, will be used to format the location template         to determine the location to write to</li></ul>**Returns**:     <ul class="args"><li class="args">`Result`: returns a new `Result` with both `value` and `location` attributes</li></ul></p>|

---
<br>

 ## S3Result
 <div class='class-sig' id='prefect-engine-results-s3-result-s3result'><p class="prefect-sig">class </p><p class="prefect-class">prefect.engine.results.s3_result.S3Result</p>(bucket, boto3_kwargs=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/results/s3_result.py#L11">[source]</a></span></div>

Result that is written to and retrieved from an AWS S3 Bucket.

For authentication, there are two options: you can provide your AWS credentials to `prefect.context.secrets.AWS_CREDENTIALS` for automatic authentication or you can [configure your flow's runtime environment](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/configuration.html#guide-configuration) for `boto3`.

See [Third Party Authentication](../../../orchestration/recipes/third_party_auth.html) for more information.

**Args**:     <ul class="args"><li class="args">`bucket (str)`: the name of the bucket to write to / read from     </li><li class="args">`boto3_kwargs (dict, optional)`: keyword arguments to pass on to boto3 when the [client         session](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/core/session.html#boto3.session.Session.client)         is initialized (changing the "service_name" is not permitted).     </li><li class="args">`**kwargs (Any, optional)`: any additional `Result` initialization options</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-engine-results-s3-result-s3result-exists'><p class="prefect-class">prefect.engine.results.s3_result.S3Result.exists</p>(location, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/results/s3_result.py#L156">[source]</a></span></div>
<p class="methods">Checks whether the target result exists in the S3 bucket.<br><br>Does not validate whether the result is `valid`, only that it is present.<br><br>**Args**:     <ul class="args"><li class="args">`location (str)`: Location of the result in the specific result target.     </li><li class="args">`**kwargs (Any)`: string format arguments for `location`</li></ul>**Returns**:     <ul class="args"><li class="args">`bool`: whether or not the target result exists.</li></ul></p>|
 | <div class='method-sig' id='prefect-engine-results-s3-result-s3result-initialize-client'><p class="prefect-class">prefect.engine.results.s3_result.S3Result.initialize_client</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/results/s3_result.py#L43">[source]</a></span></div>
<p class="methods">Initializes an S3 Client.</p>|
 | <div class='method-sig' id='prefect-engine-results-s3-result-s3result-read'><p class="prefect-class">prefect.engine.results.s3_result.S3Result.read</p>(location)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/results/s3_result.py#L116">[source]</a></span></div>
<p class="methods">Reads a result from S3, reads it and returns a new `Result` object with the corresponding value.<br><br>**Args**:     <ul class="args"><li class="args">`location (str)`: the S3 URI to read from</li></ul>**Returns**:     <ul class="args"><li class="args">`Any`: the read result</li></ul></p>|
 | <div class='method-sig' id='prefect-engine-results-s3-result-s3result-write'><p class="prefect-class">prefect.engine.results.s3_result.S3Result.write</p>(value, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/results/s3_result.py#L83">[source]</a></span></div>
<p class="methods">Writes the result to a location in S3 and returns the resulting URI.<br><br>**Args**:     <ul class="args"><li class="args">`value (Any)`: the value to write; will then be stored as the `value` attribute         of the returned `Result` instance     </li><li class="args">`**kwargs (optional)`: if provided, will be used to format the location template         to determine the location to write to</li></ul>**Returns**:     <ul class="args"><li class="args">`Result`: a new Result instance with the appropriately formatted S3 URI</li></ul></p>|

---
<br>

 ## AzureResult
 <div class='class-sig' id='prefect-engine-results-azure-result-azureresult'><p class="prefect-sig">class </p><p class="prefect-class">prefect.engine.results.azure_result.AzureResult</p>(container, connection_string=None, connection_string_secret=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/results/azure_result.py#L11">[source]</a></span></div>

Result for writing to and reading from an Azure Blob storage.

Note that your flow's runtime environment must be able to authenticate with Azure; there are currently two supported options: provide a connection string either at initialization or at runtime through an environment variable, or set your Azure connection string as a Prefect Secret.  Using an environment variable is the recommended approach.

**Args**:     <ul class="args"><li class="args">`container (str)`: the name of the container to write to / read from     </li><li class="args">`connection_string (str, optional)`: an Azure connection string for communicating with         Blob storage. If not provided the value set in the environment as         `AZURE_STORAGE_CONNECTION_STRING` will be used     </li><li class="args">`connection_string_secret (str, optional)`: the name of a Prefect Secret         which stores your Azure connection tring     </li><li class="args">`**kwargs (Any, optional)`: any additional `Result` initialization options</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-engine-results-azure-result-azureresult-exists'><p class="prefect-class">prefect.engine.results.azure_result.AzureResult.exists</p>(location, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/results/azure_result.py#L145">[source]</a></span></div>
<p class="methods">Checks whether the target result exists.<br><br>Does not validate whether the result is `valid`, only that it is present.<br><br>**Args**:     <ul class="args"><li class="args">`location (str)`: Location of the result in the specific result target.         Will check whether the provided location exists     </li><li class="args">`**kwargs (Any)`: string format arguments for `location`</li></ul>**Returns**:     <ul class="args"><li class="args">`bool`: whether or not the target result exists.</li></ul></p>|
 | <div class='method-sig' id='prefect-engine-results-azure-result-azureresult-initialize-service'><p class="prefect-class">prefect.engine.results.azure_result.AzureResult.initialize_service</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/results/azure_result.py#L45">[source]</a></span></div>
<p class="methods">Initialize a Blob service.</p>|
 | <div class='method-sig' id='prefect-engine-results-azure-result-azureresult-read'><p class="prefect-class">prefect.engine.results.azure_result.AzureResult.read</p>(location)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/results/azure_result.py#L109">[source]</a></span></div>
<p class="methods">Reads a result from an Azure Blob container and returns a corresponding `Result` instance.<br><br>**Args**:     <ul class="args"><li class="args">`location (str)`: the Azure blob location to read from</li></ul>**Returns**:     <ul class="args"><li class="args">`Result`: the read result</li></ul></p>|
 | <div class='method-sig' id='prefect-engine-results-azure-result-azureresult-write'><p class="prefect-class">prefect.engine.results.azure_result.AzureResult.write</p>(value, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/results/azure_result.py#L78">[source]</a></span></div>
<p class="methods">Writes the result value to a blob storage in Azure.<br><br>**Args**:     <ul class="args"><li class="args">`value (Any)`: the value to write; will then be stored as the `value` attribute         of the returned `Result` instance     </li><li class="args">`**kwargs (optional)`: if provided, will be used to format the location template         to determine the location to write to</li></ul>**Returns**:     <ul class="args"><li class="args">`Result`: a new Result instance with the appropriately formatted location</li></ul></p>|

---
<br>

 ## SecretResult
 <div class='class-sig' id='prefect-engine-results-secret-result-secretresult'><p class="prefect-sig">class </p><p class="prefect-class">prefect.engine.results.secret_result.SecretResult</p>(secret_task, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/results/secret_result.py#L7">[source]</a></span></div>

Hook for storing and retrieving sensitive task results from a Secret store. Only intended to be used for Secret Tasks - each call to "read" will actually rerun the underlying secret task and re-retrieve the secret value.

**Args**:     <ul class="args"><li class="args">`secret_task (Task)`: the Secret Task this result wraps     </li><li class="args">`**kwargs (Any, optional)`: additional kwargs to pass to the `Result` initialization</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-engine-results-secret-result-secretresult-read'><p class="prefect-class">prefect.engine.results.secret_result.SecretResult.read</p>(location)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/results/secret_result.py#L27">[source]</a></span></div>
<p class="methods">Returns the Secret Value corresponding to the passed name.<br><br>**Args**:     <ul class="args"><li class="args">`location (str)`: the name of the Secret to retrieve</li></ul>**Returns**:     <ul class="args"><li class="args">`Result`: a new result instance with the data represented by the location</li></ul></p>|
 | <div class='method-sig' id='prefect-engine-results-secret-result-secretresult-write'><p class="prefect-class">prefect.engine.results.secret_result.SecretResult.write</p>(value, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/results/secret_result.py#L42">[source]</a></span></div>
<p class="methods">Secret results cannot be written to; provided for interface compatibility.<br><br>**Args**:     <ul class="args"><li class="args">`value (Any)`: unused, for interface compatibility     </li><li class="args">`**kwargs (optional)`: unused, for interface compatibility</li></ul>**Raises**:     <ul class="args"><li class="args">`ValueError`: SecretResults cannot be written to</li></ul></p>|

---
<br>

 ## ConstantResult
 <div class='class-sig' id='prefect-engine-results-constant-result-constantresult'><p class="prefect-sig">class </p><p class="prefect-class">prefect.engine.results.constant_result.ConstantResult</p>(**kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/results/constant_result.py#L5">[source]</a></span></div>

Hook for storing and retrieving constant Python objects. Only intended to be used internally.  The "backend" in this instance is the class instance itself.

**Args**:     <ul class="args"><li class="args">`**kwargs (Any, optional)`: any additional `Result` initialization options</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-engine-results-constant-result-constantresult-exists'><p class="prefect-class">prefect.engine.results.constant_result.ConstantResult.exists</p>(location, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/results/constant_result.py#L41">[source]</a></span></div>
<p class="methods">As all Python objects are valid constants, always returns `True`.<br><br>**Args**:      <ul class="args"><li class="args">`location (str)`: for interface compatibility      </li><li class="args">`**kwargs (Any)`: string format arguments for `location`</li></ul>**Returns**:     <ul class="args"><li class="args">`bool`: True, confirming the constant exists.</li></ul></p>|
 | <div class='method-sig' id='prefect-engine-results-constant-result-constantresult-read'><p class="prefect-class">prefect.engine.results.constant_result.ConstantResult.read</p>(location)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/results/constant_result.py#L19">[source]</a></span></div>
<p class="methods">Will return the underlying value regardless of the argument passed.<br><br>**Args**:     <ul class="args"><li class="args">`location (str)`: an unused argument</li></ul></p>|
 | <div class='method-sig' id='prefect-engine-results-constant-result-constantresult-write'><p class="prefect-class">prefect.engine.results.constant_result.ConstantResult.write</p>(value, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/results/constant_result.py#L28">[source]</a></span></div>
<p class="methods">Will return the repr of the underlying value, purely for convenience.<br><br>**Args**:     <ul class="args"><li class="args">`value (Any)`: unused, for interface compatibility     </li><li class="args">`**kwargs (optional)`: unused, for interface compatibility</li></ul>**Raises**:     <ul class="args"><li class="args">`ValueError`: ConstantResults cannot be written to</li></ul></p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on August 6, 2020 at 13:56 UTC</p>