---
sidebarDepth: 2
editLink: false
---
# Result Handlers
---
Result handler is simply a specific implementation of a `read` / `write` interface for handling data.
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
<p class="methods">Read a result from a string JSON blob.<br><br>**Args**:     <ul class="args"><li class="args">`jblob (str)`: the JSON representation of the result</li></ul>**Returns**:     <ul class="args"><li class="args">`Any`: the deserialized result</li></ul></p>|
 | <div class='method-sig' id='prefect-engine-result-handlers-json-result-handler-jsonresulthandler-write'><p class="prefect-class">prefect.engine.result_handlers.json_result_handler.JSONResultHandler.write</p>(result)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/result_handlers/json_result_handler.py#L25">[source]</a></span></div>
<p class="methods">Serialize the provided result to JSON.<br><br>**Args**:     <ul class="args"><li class="args">`result (Any)`: the result to write</li></ul>**Returns**:     <ul class="args"><li class="args">`str`: the JSON representation of the result</li></ul></p>|

---
<br>

 ## GCSResultHandler
 <div class='class-sig' id='prefect-engine-result-handlers-gcs-result-handler-gcsresulthandler'><p class="prefect-sig">class </p><p class="prefect-class">prefect.engine.result_handlers.gcs_result_handler.GCSResultHandler</p>(bucket=None, credentials_secret="GOOGLE_APPLICATION_CREDENTIALS")<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/result_handlers/gcs_result_handler.py#L15">[source]</a></span></div>

Result Handler for writing to and reading from a Google Cloud Bucket.

**Args**:     <ul class="args"><li class="args">`bucket (str)`: the name of the bucket to write to / read from     </li><li class="args">`credentials_secret (str, optional)`: the name of the Prefect Secret         which stores a JSON representation of your Google Cloud credentials.         Defaults to `GOOGLE_APPLICATION_CREDENTIALS`.</li></ul>Note that for this result handler to work properly, your Google Application Credentials must be made available.

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-engine-result-handlers-gcs-result-handler-gcsresulthandler-initialize-client'><p class="prefect-class">prefect.engine.result_handlers.gcs_result_handler.GCSResultHandler.initialize_client</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/result_handlers/gcs_result_handler.py#L38">[source]</a></span></div>
<p class="methods">Initializes GCS connections.</p>|
 | <div class='method-sig' id='prefect-engine-result-handlers-gcs-result-handler-gcsresulthandler-read'><p class="prefect-class">prefect.engine.result_handlers.gcs_result_handler.GCSResultHandler.read</p>(uri)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/result_handlers/gcs_result_handler.py#L89">[source]</a></span></div>
<p class="methods">Given a uri, reads a result from GCS, reads it and returns it<br><br>**Args**:     <ul class="args"><li class="args">`uri (str)`: the GCS URI</li></ul>**Returns**:     <ul class="args"><li class="args">`Any`: the read result</li></ul></p>|
 | <div class='method-sig' id='prefect-engine-result-handlers-gcs-result-handler-gcsresulthandler-write'><p class="prefect-class">prefect.engine.result_handlers.gcs_result_handler.GCSResultHandler.write</p>(result)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/result_handlers/gcs_result_handler.py#L70">[source]</a></span></div>
<p class="methods">Given a result, writes the result to a location in GCS and returns the resulting URI.<br><br>**Args**:     <ul class="args"><li class="args">`result (Any)`: the written result</li></ul>**Returns**:     <ul class="args"><li class="args">`str`: the GCS URI</li></ul></p>|

---
<br>

 ## LocalResultHandler
 <div class='class-sig' id='prefect-engine-result-handlers-local-result-handler-localresulthandler'><p class="prefect-sig">class </p><p class="prefect-class">prefect.engine.result_handlers.local_result_handler.LocalResultHandler</p>(dir=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/result_handlers/local_result_handler.py#L15">[source]</a></span></div>

Hook for storing and retrieving task results from local file storage. Only intended to be used for local testing and development. Task results are written using `cloudpickle` and stored in the provided location for use in future runs.

**NOTE**: Stored results will _not_ be automatically cleaned up after execution.

**Args**:     <ul class="args"><li class="args">`dir (str, optional)`: the _absolute_ path to a directory for storing         all results; defaults to `$TMPDIR`</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-engine-result-handlers-local-result-handler-localresulthandler-read'><p class="prefect-class">prefect.engine.result_handlers.local_result_handler.LocalResultHandler.read</p>(fpath)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/result_handlers/local_result_handler.py#L32">[source]</a></span></div>
<p class="methods">Read a result from the given file location.<br><br>**Args**:     <ul class="args"><li class="args">`fpath (str)`: the _absolute_ path to the location of a written result</li></ul>**Returns**:     <ul class="args"><li class="args">the read result from the provided file</li></ul></p>|
 | <div class='method-sig' id='prefect-engine-result-handlers-local-result-handler-localresulthandler-write'><p class="prefect-class">prefect.engine.result_handlers.local_result_handler.LocalResultHandler.write</p>(result)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/result_handlers/local_result_handler.py#L48">[source]</a></span></div>
<p class="methods">Serialize the provided result to local disk.<br><br>**Args**:     <ul class="args"><li class="args">`result (Any)`: the result to write and store</li></ul>**Returns**:     <ul class="args"><li class="args">`str`: the _absolute_ path to the written result on disk</li></ul></p>|

---
<br>

 ## S3ResultHandler
 <div class='class-sig' id='prefect-engine-result-handlers-s3-result-handler-s3resulthandler'><p class="prefect-sig">class </p><p class="prefect-class">prefect.engine.result_handlers.s3_result_handler.S3ResultHandler</p>(bucket=None, aws_credentials_secret="AWS_CREDENTIALS")<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/result_handlers/s3_result_handler.py#L17">[source]</a></span></div>

Result Handler for writing to and reading from an AWS S3 Bucket.

**Args**:     <ul class="args"><li class="args">`bucket (str)`: the name of the bucket to write to / read from     </li><li class="args">`aws_credentials_secret (str, optional)`: the name of the Prefect Secret         which stores your AWS credentials; this Secret must be a JSON string         with two keys: `ACCESS_KEY` and `SECRET_ACCESS_KEY`</li></ul>Note that for this result handler to work properly, your AWS Credentials must be made available in the `"AWS_CREDENTIALS"` Prefect Secret.

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-engine-result-handlers-s3-result-handler-s3resulthandler-initialize-client'><p class="prefect-class">prefect.engine.result_handlers.s3_result_handler.S3ResultHandler.initialize_client</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/result_handlers/s3_result_handler.py#L38">[source]</a></span></div>
<p class="methods">Initializes an S3 Client.</p>|
 | <div class='method-sig' id='prefect-engine-result-handlers-s3-result-handler-s3resulthandler-read'><p class="prefect-class">prefect.engine.result_handlers.s3_result_handler.S3ResultHandler.read</p>(uri)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/result_handlers/s3_result_handler.py#L100">[source]</a></span></div>
<p class="methods">Given a uri, reads a result from S3, reads it and returns it<br><br>**Args**:     <ul class="args"><li class="args">`uri (str)`: the S3 URI</li></ul>**Returns**:     <ul class="args"><li class="args">`Any`: the read result</li></ul></p>|
 | <div class='method-sig' id='prefect-engine-result-handlers-s3-result-handler-s3resulthandler-write'><p class="prefect-class">prefect.engine.result_handlers.s3_result_handler.S3ResultHandler.write</p>(result)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/result_handlers/s3_result_handler.py#L76">[source]</a></span></div>
<p class="methods">Given a result, writes the result to a location in S3 and returns the resulting URI.<br><br>**Args**:     <ul class="args"><li class="args">`result (Any)`: the written result</li></ul>**Returns**:     <ul class="args"><li class="args">`str`: the S3 URI</li></ul></p>|

---
<br>

 ## AzureResultHandler
 <div class='class-sig' id='prefect-engine-result-handlers-azure-result-handler-azureresulthandler'><p class="prefect-sig">class </p><p class="prefect-class">prefect.engine.result_handlers.azure_result_handler.AzureResultHandler</p>(container=None, azure_credentials_secret="AZ_CREDENTIALS")<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/result_handlers/azure_result_handler.py#L16">[source]</a></span></div>

Result Handler for writing to and reading from an Azure Blob storage.

**Args**:     <ul class="args"><li class="args">`container (str)`: the name of the container to write to / read from     </li><li class="args">`azure_credentials_secret (str, optional)`: the name of the Prefect Secret         which stores your Azure credentials; this Secret must be a JSON string         with two keys: `ACCOUNT_NAME` and either `ACCOUNT_KEY` or `SAS_TOKEN`          (if both are defined then`ACCOUNT_KEY` is used)</li></ul>Note that for this result handler to work properly, your Azure Credentials must be made available in the `"AZ_CREDENTIALS"` Prefect Secret.

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-engine-result-handlers-azure-result-handler-azureresulthandler-initialize-service'><p class="prefect-class">prefect.engine.result_handlers.azure_result_handler.AzureResultHandler.initialize_service</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/result_handlers/azure_result_handler.py#L38">[source]</a></span></div>
<p class="methods">Initialize a Blob service.</p>|
 | <div class='method-sig' id='prefect-engine-result-handlers-azure-result-handler-azureresulthandler-read'><p class="prefect-class">prefect.engine.result_handlers.azure_result_handler.AzureResultHandler.read</p>(uri)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/result_handlers/azure_result_handler.py#L105">[source]</a></span></div>
<p class="methods">Given a uri, reads a result from Azure Blob storage, reads it and returns it<br><br>**Args**:     <ul class="args"><li class="args">`uri (str)`: the Azure Blob URI</li></ul>**Returns**:     <ul class="args"><li class="args">`Any`: the read result</li></ul></p>|
 | <div class='method-sig' id='prefect-engine-result-handlers-azure-result-handler-azureresulthandler-write'><p class="prefect-class">prefect.engine.result_handlers.azure_result_handler.AzureResultHandler.write</p>(result)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/result_handlers/azure_result_handler.py#L78">[source]</a></span></div>
<p class="methods">Given a result, writes the result to a location in Azure Blob storage and returns the resulting URI.<br><br>**Args**:     <ul class="args"><li class="args">`result (Any)`: the written result</li></ul>**Returns**:     <ul class="args"><li class="args">`str`: the Blob URI</li></ul></p>|

---
<br>

 ## SecretResultHandler
 <div class='class-sig' id='prefect-engine-result-handlers-secret-result-handler-secretresulthandler'><p class="prefect-sig">class </p><p class="prefect-class">prefect.engine.result_handlers.secret_result_handler.SecretResultHandler</p>(secret_task)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/result_handlers/secret_result_handler.py#L8">[source]</a></span></div>

Hook for storing and retrieving sensitive task results from a Secret store. Only intended to be used for Secret tasks.

**Args**:     <ul class="args"><li class="args">`secret_task (Task)`: the Secret Task that this result handler will be used for</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-engine-result-handlers-secret-result-handler-secretresulthandler-read'><p class="prefect-class">prefect.engine.result_handlers.secret_result_handler.SecretResultHandler.read</p>(name)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/result_handlers/secret_result_handler.py#L21">[source]</a></span></div>
<p class="methods">Read a secret from a provided name with the provided Secret class; this method actually retrieves the secret from the Secret store.<br><br>**Args**:     <ul class="args"><li class="args">`name (str)`: the name of the secret to retrieve</li></ul>**Returns**:     <ul class="args"><li class="args">`Any`: the deserialized result</li></ul></p>|
 | <div class='method-sig' id='prefect-engine-result-handlers-secret-result-handler-secretresulthandler-write'><p class="prefect-class">prefect.engine.result_handlers.secret_result_handler.SecretResultHandler.write</p>(result)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/result_handlers/secret_result_handler.py#L34">[source]</a></span></div>
<p class="methods">Returns the name of the secret.<br><br>**Args**:     <ul class="args"><li class="args">`result (Any)`: the result to write</li></ul>**Returns**:     <ul class="args"><li class="args">`str`: the JSON representation of the result</li></ul></p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on October 29, 2019 at 19:43 UTC</p>