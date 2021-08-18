---
sidebarDepth: 2
editLink: false
---
# Result Handlers
---
:::warning
Result handlers have been deprecated in 0.11.0. For Prefect installations 0.11.0+, at runtime, all result handlers configured on a flow will be autoconverted into a matching subclass of `Result` from `prefect.engine.results`.
:::

Result handler is a specific implementation of a `read` / `write` interface for handling data.
The only requirement for a Result handler implementation is that the `write` method returns a JSON-compatible object.

As a toy example, suppose we want to implement a result handler which stores data on some webserver that we have access to.
Our custom result handler might look like:

```python
import json
import requests
from prefect.engine.result_handlers import ResultHandler


class WebServerHandler(ResultHandler):
    def write(self, obj):
        '''
        Stores a JSON-compatible object on our webserver and returns
        the URL for retrieving it later
        '''
        r = requests.post("http://foo.example.bar/", data={"payload": json.dumps(obj)})
        url = r.json()['url']
        return url

    def read(self, url):
        '''
        Given a URL on our webserver, retrieves the object and deserializes it.
        '''
        r = requests.get(url)
        json_obj = r.json()['payload']
        return json.loads(json_obj)
```

Note that we could also optionally override the `__init__` method of our class if we wanted to allow for additional configuration.
 ## JSONResultHandler
 <div class='class-sig' id='prefect-engine-result-handlers-json-result-handler-jsonresulthandler'><p class="prefect-sig">class </p><p class="prefect-class">prefect.engine.result_handlers.json_result_handler.JSONResultHandler</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/result_handlers/json_result_handler.py#L7">[source]</a></span></div>

Hook for storing and retrieving task results to / from JSON. Only intended to be used for small data loads.

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-engine-result-handlers-json-result-handler-jsonresulthandler-read'><p class="prefect-class">prefect.engine.result_handlers.json_result_handler.JSONResultHandler.read</p>(jblob)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/result_handlers/json_result_handler.py#L13">[source]</a></span></div>
<p class="methods">Read a result from a string JSON blob.<br><br>**Args**:     <ul class="args"><li class="args">`jblob (str)`: the JSON representation of the result</li></ul> **Returns**:     <ul class="args"><li class="args">`Any`: the deserialized result</li></ul></p>|
 | <div class='method-sig' id='prefect-engine-result-handlers-json-result-handler-jsonresulthandler-write'><p class="prefect-class">prefect.engine.result_handlers.json_result_handler.JSONResultHandler.write</p>(result)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/result_handlers/json_result_handler.py#L25">[source]</a></span></div>
<p class="methods">Serialize the provided result to JSON.<br><br>**Args**:     <ul class="args"><li class="args">`result (Any)`: the result to write</li></ul> **Returns**:     <ul class="args"><li class="args">`str`: the JSON representation of the result</li></ul></p>|

---
<br>

 ## GCSResultHandler
 <div class='class-sig' id='prefect-engine-result-handlers-gcs-result-handler-gcsresulthandler'><p class="prefect-sig">class </p><p class="prefect-class">prefect.engine.result_handlers.gcs_result_handler.GCSResultHandler</p>(bucket=None, credentials_secret=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/result_handlers/gcs_result_handler.py#L15">[source]</a></span></div>

Result Handler for writing to and reading from a Google Cloud Bucket.

To authenticate with Google Cloud, you need to ensure that your flow's runtime environment has the proper credentials available (see https://cloud.google.com/docs/authentication/production for all the authentication options).

You can also optionally provide the name of a Prefect Secret containing your service account key.

**Args**:     <ul class="args"><li class="args">`bucket (str)`: the name of the bucket to write to / read from     </li><li class="args">`credentials_secret (str, optional)`: the name of the Prefect Secret         which stores a JSON representation of your Google Cloud credentials.</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-engine-result-handlers-gcs-result-handler-gcsresulthandler-initialize-client'><p class="prefect-class">prefect.engine.result_handlers.gcs_result_handler.GCSResultHandler.initialize_client</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/result_handlers/gcs_result_handler.py#L38">[source]</a></span></div>
<p class="methods">Initializes GCS connections.</p>|
 | <div class='method-sig' id='prefect-engine-result-handlers-gcs-result-handler-gcsresulthandler-read'><p class="prefect-class">prefect.engine.result_handlers.gcs_result_handler.GCSResultHandler.read</p>(uri)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/result_handlers/gcs_result_handler.py#L89">[source]</a></span></div>
<p class="methods">Given a uri, reads a result from GCS, reads it and returns it<br><br>**Args**:     <ul class="args"><li class="args">`uri (str)`: the GCS URI</li></ul> **Returns**:     <ul class="args"><li class="args">`Any`: the read result</li></ul></p>|
 | <div class='method-sig' id='prefect-engine-result-handlers-gcs-result-handler-gcsresulthandler-write'><p class="prefect-class">prefect.engine.result_handlers.gcs_result_handler.GCSResultHandler.write</p>(result)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/result_handlers/gcs_result_handler.py#L70">[source]</a></span></div>
<p class="methods">Given a result, writes the result to a location in GCS and returns the resulting URI.<br><br>**Args**:     <ul class="args"><li class="args">`result (Any)`: the written result</li></ul> **Returns**:     <ul class="args"><li class="args">`str`: the GCS URI</li></ul></p>|

---
<br>

 ## LocalResultHandler
 <div class='class-sig' id='prefect-engine-result-handlers-local-result-handler-localresulthandler'><p class="prefect-sig">class </p><p class="prefect-class">prefect.engine.result_handlers.local_result_handler.LocalResultHandler</p>(dir=None, validate=True)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/result_handlers/local_result_handler.py#L19">[source]</a></span></div>

Hook for storing and retrieving task results from local file storage. Task results are written using `cloudpickle` and stored in the provided location for use in future runs.

**Args**:     <ul class="args"><li class="args">`dir (str, optional)`: the _absolute_ path to a directory for storing         all results; defaults to `${prefect.config.home_dir}/results`     </li><li class="args">`validate (bool, optional)`: a boolean specifying whether to validate the         provided directory path; if `True`, the directory will be converted to an         absolute path and created.  Defaults to `True`</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-engine-result-handlers-local-result-handler-localresulthandler-read'><p class="prefect-class">prefect.engine.result_handlers.local_result_handler.LocalResultHandler.read</p>(fpath)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/result_handlers/local_result_handler.py#L53">[source]</a></span></div>
<p class="methods">Read a result from the given file location.<br><br>**Args**:     <ul class="args"><li class="args">`fpath (str)`: the _absolute_ path to the location of a written result</li></ul> **Returns**:     <ul class="args"><li class="args">the read result from the provided file</li></ul></p>|
 | <div class='method-sig' id='prefect-engine-result-handlers-local-result-handler-localresulthandler-write'><p class="prefect-class">prefect.engine.result_handlers.local_result_handler.LocalResultHandler.write</p>(result)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/result_handlers/local_result_handler.py#L69">[source]</a></span></div>
<p class="methods">Serialize the provided result to local disk.<br><br>**Args**:     <ul class="args"><li class="args">`result (Any)`: the result to write and store</li></ul> **Returns**:     <ul class="args"><li class="args">`str`: the _absolute_ path to the written result on disk</li></ul></p>|

---
<br>

 ## S3ResultHandler
 <div class='class-sig' id='prefect-engine-result-handlers-s3-result-handler-s3resulthandler'><p class="prefect-sig">class </p><p class="prefect-class">prefect.engine.result_handlers.s3_result_handler.S3ResultHandler</p>(bucket, aws_credentials_secret=None, boto3_kwargs=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/result_handlers/s3_result_handler.py#L18">[source]</a></span></div>

Result Handler for writing to and reading from an AWS S3 Bucket.

For authentication, there are two options: you can set a Prefect Secret containing your AWS access keys which will be passed directly to the `boto3` client, or you can [configure your flow's runtime environment](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/configuration.html#guide-configuration) for `boto3`.

**Args**:     <ul class="args"><li class="args">`bucket (str)`: the name of the bucket to write to / read from     </li><li class="args">`aws_credentials_secret (str, optional)`: the name of the Prefect Secret         that stores your AWS credentials; this Secret must be a JSON string         with two keys: `ACCESS_KEY` and `SECRET_ACCESS_KEY` which will be         passed directly to `boto3`.  If not provided, `boto3`         will fall back on standard AWS rules for authentication.     </li><li class="args">`boto3_kwargs (dict, optional)`: keyword arguments to pass on to boto3 when the [client         session](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/core/session.html#boto3.session.Session.client)         is initialized (changing the "service_name" is not permitted).</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-engine-result-handlers-s3-result-handler-s3resulthandler-initialize-client'><p class="prefect-class">prefect.engine.result_handlers.s3_result_handler.S3ResultHandler.initialize_client</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/result_handlers/s3_result_handler.py#L55">[source]</a></span></div>
<p class="methods">Initializes an S3 Client.</p>|
 | <div class='method-sig' id='prefect-engine-result-handlers-s3-result-handler-s3resulthandler-read'><p class="prefect-class">prefect.engine.result_handlers.s3_result_handler.S3ResultHandler.read</p>(uri)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/result_handlers/s3_result_handler.py#L140">[source]</a></span></div>
<p class="methods">Given a uri, reads a result from S3, reads it and returns it<br><br>**Args**:     <ul class="args"><li class="args">`uri (str)`: the S3 URI</li></ul> **Returns**:     <ul class="args"><li class="args">`Any`: the read result</li></ul></p>|
 | <div class='method-sig' id='prefect-engine-result-handlers-s3-result-handler-s3resulthandler-write'><p class="prefect-class">prefect.engine.result_handlers.s3_result_handler.S3ResultHandler.write</p>(result)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/result_handlers/s3_result_handler.py#L116">[source]</a></span></div>
<p class="methods">Given a result, writes the result to a location in S3 and returns the resulting URI.<br><br>**Args**:     <ul class="args"><li class="args">`result (Any)`: the written result</li></ul> **Returns**:     <ul class="args"><li class="args">`str`: the S3 URI</li></ul></p>|

---
<br>

 ## AzureResultHandler
 <div class='class-sig' id='prefect-engine-result-handlers-azure-result-handler-azureresulthandler'><p class="prefect-sig">class </p><p class="prefect-class">prefect.engine.result_handlers.azure_result_handler.AzureResultHandler</p>(container, connection_string=None, azure_credentials_secret="AZ_CREDENTIALS")<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/result_handlers/azure_result_handler.py#L17">[source]</a></span></div>

Result Handler for writing to and reading from an Azure Blob storage.

Note that your flow's runtime environment must be able to authenticate with Azure; there are currently two supported options: provide a connection string either at initialization or at runtime through an environment variable, or set your Azure credentials as a Prefect Secret.  Using an environment variable is the recommended approach.

**Args**:     <ul class="args"><li class="args">`container (str)`: the name of the container to write to / read from     </li><li class="args">`connection_string (str, optional)`: an Azure connection string for communicating with         Blob storage. If not provided the value set in the environment as         `AZURE_STORAGE_CONNECTION_STRING` will be used     </li><li class="args">`azure_credentials_secret (str, optional)`: the name of a Prefect Secret         which stores your Azure credentials; this Secret must be a JSON payload         with two keys: `ACCOUNT_NAME` and either `ACCOUNT_KEY` or `SAS_TOKEN`         (if both are defined then`ACCOUNT_KEY` is used)</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-engine-result-handlers-azure-result-handler-azureresulthandler-initialize-service'><p class="prefect-class">prefect.engine.result_handlers.azure_result_handler.AzureResultHandler.initialize_service</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/result_handlers/azure_result_handler.py#L50">[source]</a></span></div>
<p class="methods">Initialize a Blob service.</p>|
 | <div class='method-sig' id='prefect-engine-result-handlers-azure-result-handler-azureresulthandler-read'><p class="prefect-class">prefect.engine.result_handlers.azure_result_handler.AzureResultHandler.read</p>(uri)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/result_handlers/azure_result_handler.py#L117">[source]</a></span></div>
<p class="methods">Given a uri, reads a result from Azure Blob storage, reads it and returns it<br><br>**Args**:     <ul class="args"><li class="args">`uri (str)`: the Azure Blob URI</li></ul> **Returns**:     <ul class="args"><li class="args">`Any`: the read result</li></ul></p>|
 | <div class='method-sig' id='prefect-engine-result-handlers-azure-result-handler-azureresulthandler-write'><p class="prefect-class">prefect.engine.result_handlers.azure_result_handler.AzureResultHandler.write</p>(result)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/result_handlers/azure_result_handler.py#L90">[source]</a></span></div>
<p class="methods">Given a result, writes the result to a location in Azure Blob storage and returns the resulting URI.<br><br>**Args**:     <ul class="args"><li class="args">`result (Any)`: the written result</li></ul> **Returns**:     <ul class="args"><li class="args">`str`: the Blob URI</li></ul></p>|

---
<br>

 ## SecretResultHandler
 <div class='class-sig' id='prefect-engine-result-handlers-secret-result-handler-secretresulthandler'><p class="prefect-sig">class </p><p class="prefect-class">prefect.engine.result_handlers.secret_result_handler.SecretResultHandler</p>(secret_task)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/result_handlers/secret_result_handler.py#L7">[source]</a></span></div>

Hook for storing and retrieving sensitive task results from a Secret store. Only intended to be used for Secret tasks.

**Args**:     <ul class="args"><li class="args">`secret_task (Task)`: the Secret Task that this result handler will be used for</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-engine-result-handlers-secret-result-handler-secretresulthandler-read'><p class="prefect-class">prefect.engine.result_handlers.secret_result_handler.SecretResultHandler.read</p>(name)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/result_handlers/secret_result_handler.py#L20">[source]</a></span></div>
<p class="methods">Read a secret from a provided name with the provided Secret class; this method actually retrieves the secret from the Secret store.<br><br>**Args**:     <ul class="args"><li class="args">`name (str)`: the name of the secret to retrieve</li></ul> **Returns**:     <ul class="args"><li class="args">`Any`: the deserialized result</li></ul></p>|
 | <div class='method-sig' id='prefect-engine-result-handlers-secret-result-handler-secretresulthandler-write'><p class="prefect-class">prefect.engine.result_handlers.secret_result_handler.SecretResultHandler.write</p>(result)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/result_handlers/secret_result_handler.py#L33">[source]</a></span></div>
<p class="methods">Returns the name of the secret.<br><br>**Args**:     <ul class="args"><li class="args">`result (Any)`: the result to write</li></ul> **Returns**:     <ul class="args"><li class="args">`str`: the JSON representation of the result</li></ul></p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on December 16, 2020 at 21:36 UTC</p>