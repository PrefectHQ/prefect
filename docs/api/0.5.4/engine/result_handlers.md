---
sidebarDepth: 2
editLink: false
---
# Result Handlers
---
Result handler is simply a specific implementation of a `read` / `write` interface for handling data.
The only requirement for a Result handler implementation is that the `write` method returns a JSON-compatible object.
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
 <div class='class-sig' id='prefect-engine-result-handlers-gcs-result-handler-gcsresulthandler'><p class="prefect-sig">class </p><p class="prefect-class">prefect.engine.result_handlers.gcs_result_handler.GCSResultHandler</p>(bucket=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/result_handlers/gcs_result_handler.py#L15">[source]</a></span></div>

Result Handler for writing to and reading from a Google Cloud Bucket.

**Args**:     <ul class="args"><li class="args">`bucket (str)`: the name of the bucket to write to / read from</li></ul>Note that for this result handler to work properly, your Google Application Credentials must be made available.

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-engine-result-handlers-gcs-result-handler-gcsresulthandler-initialize-client'><p class="prefect-class">prefect.engine.result_handlers.gcs_result_handler.GCSResultHandler.initialize_client</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/result_handlers/gcs_result_handler.py#L31">[source]</a></span></div>
<p class="methods">Initializes GCS connections.</p>|
 | <div class='method-sig' id='prefect-engine-result-handlers-gcs-result-handler-gcsresulthandler-read'><p class="prefect-class">prefect.engine.result_handlers.gcs_result_handler.GCSResultHandler.read</p>(uri)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/result_handlers/gcs_result_handler.py#L82">[source]</a></span></div>
<p class="methods">Given a uri, reads a result from GCS, reads it and returns it<br><br>**Args**:     <ul class="args"><li class="args">`uri (str)`: the GCS URI</li></ul>**Returns**:     <ul class="args"><li class="args">`Any`: the read result</li></ul></p>|
 | <div class='method-sig' id='prefect-engine-result-handlers-gcs-result-handler-gcsresulthandler-write'><p class="prefect-class">prefect.engine.result_handlers.gcs_result_handler.GCSResultHandler.write</p>(result)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/result_handlers/gcs_result_handler.py#L63">[source]</a></span></div>
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
 <div class='class-sig' id='prefect-engine-result-handlers-s3-result-handler-s3resulthandler'><p class="prefect-sig">class </p><p class="prefect-class">prefect.engine.result_handlers.s3_result_handler.S3ResultHandler</p>(bucket=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/result_handlers/s3_result_handler.py#L17">[source]</a></span></div>

Result Handler for writing to and reading from an AWS S3 Bucket.

**Args**:     <ul class="args"><li class="args">`bucket (str)`: the name of the bucket to write to / read from</li></ul>Note that for this result handler to work properly, your AWS Credentials must be made available in the `"AWS_CREDENTIALS"` Prefect Secret.

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-engine-result-handlers-s3-result-handler-s3resulthandler-initialize-client'><p class="prefect-class">prefect.engine.result_handlers.s3_result_handler.S3ResultHandler.initialize_client</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/result_handlers/s3_result_handler.py#L33">[source]</a></span></div>
<p class="methods">Initializes an S3 Client.</p>|
 | <div class='method-sig' id='prefect-engine-result-handlers-s3-result-handler-s3resulthandler-read'><p class="prefect-class">prefect.engine.result_handlers.s3_result_handler.S3ResultHandler.read</p>(uri)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/result_handlers/s3_result_handler.py#L95">[source]</a></span></div>
<p class="methods">Given a uri, reads a result from S3, reads it and returns it<br><br>**Args**:     <ul class="args"><li class="args">`uri (str)`: the S3 URI</li></ul>**Returns**:     <ul class="args"><li class="args">`Any`: the read result</li></ul></p>|
 | <div class='method-sig' id='prefect-engine-result-handlers-s3-result-handler-s3resulthandler-write'><p class="prefect-class">prefect.engine.result_handlers.s3_result_handler.S3ResultHandler.write</p>(result)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/result_handlers/s3_result_handler.py#L71">[source]</a></span></div>
<p class="methods">Given a result, writes the result to a location in S3 and returns the resulting URI.<br><br>**Args**:     <ul class="args"><li class="args">`result (Any)`: the written result</li></ul>**Returns**:     <ul class="args"><li class="args">`str`: the S3 URI</li></ul></p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>by Prefect 0.5.3+275.g38ab4505 on May 28, 2019 at 20:38 UTC</p>