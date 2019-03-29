---
sidebarDepth: 2
editLink: false
---
# AWS Tasks
---
This module contains a collection of tasks for interacting with AWS resources.

Note that all tasks require a Prefect Secret called `"AWS_CREDENTIALS"` which should be a JSON
document with two keys: `"ACCESS_KEY"` and `"SECRET_ACCESS_KEY"`.
 ## S3Download
 <div class='class-sig' id='prefect-tasks-aws-s3-s3download'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.aws.s3.S3Download</p>(aws_credentials_secret="AWS_CREDENTIALS", bucket=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/aws/s3.py#L10">[source]</a></span></div>

Task for downloading data from an S3 bucket and returning it as a string. Note that all initialization arguments can optionally be provided or overwritten at runtime.

**Args**:     <ul class="args"><li class="args">`aws_credentials_secret (str, optional)`: the name of the Prefect Secret         which stores your AWS credentials; this Secret must be a JSON string         with two keys: `ACCESS_KEY` and `SECRET_ACCESS_KEY`     </li><li class="args">`bucket (str, optional)`: the name of the S3 Bucket to download from     </li><li class="args">`**kwargs (dict, optional)`: additional keyword arguments to pass to the         Task constructor</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-aws-s3-s3download-run'><p class="prefect-class">prefect.tasks.aws.s3.S3Download.run</p>(key, aws_credentials_secret="AWS_CREDENTIALS", bucket=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/aws/s3.py#L34">[source]</a></span></div>
<p class="methods">Task run method.<br><br>**Args**:     <ul class="args"><li class="args">`key (str)`: the name of the Key within this bucket to retrieve     </li><li class="args">`aws_credentials_secret (str, optional)`: the name of the Prefect Secret         which stores your AWS credentials; this Secret must be a JSON string         with two keys: `ACCESS_KEY` and `SECRET_ACCESS_KEY`     </li><li class="args">`bucket (str, optional)`: the name of the S3 Bucket to download from</li></ul>**Returns**:     <ul class="args"><li class="args">`str`: the contents of this Key / Bucket, as a string</li></ul></p>|

---
<br>

 ## S3Upload
 <div class='class-sig' id='prefect-tasks-aws-s3-s3upload'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.aws.s3.S3Upload</p>(aws_credentials_secret="AWS_CREDENTIALS", bucket=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/aws/s3.py#L78">[source]</a></span></div>

Task for uploading string data (e.g., a JSON string) to an S3 bucket. Note that all initialization arguments can optionally be provided or overwritten at runtime.

**Args**:     <ul class="args"><li class="args">`aws_credentials_secret (str, optional)`: the name of the Prefect Secret         which stores your AWS credentials; this Secret must be a JSON string         with two keys: `ACCESS_KEY` and `SECRET_ACCESS_KEY`     </li><li class="args">`bucket (str, optional)`: the name of the S3 Bucket to upload to     </li><li class="args">`**kwargs (dict, optional)`: additional keyword arguments to pass to the         Task constructor</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-aws-s3-s3upload-run'><p class="prefect-class">prefect.tasks.aws.s3.S3Upload.run</p>(data, key=None, aws_credentials_secret="AWS_CREDENTIALS", bucket=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/aws/s3.py#L102">[source]</a></span></div>
<p class="methods">Task run method.<br><br>**Args**:     <ul class="args"><li class="args">`data (str)`: the data payload to upload     </li><li class="args">`key (str, optional)`: the Key to upload the data under; if not         provided, a random `uuid` will be created     </li><li class="args">`aws_credentials_secret (str, optional)`: the name of the Prefect Secret         which stores your AWS credentials; this Secret must be a JSON string         with two keys: `ACCESS_KEY` and `SECRET_ACCESS_KEY`     </li><li class="args">`bucket (str, optional)`: the name of the S3 Bucket to upload to</li></ul>**Returns**:     <ul class="args"><li class="args">`str`: the name of the Key the data payload was uploaded to</li></ul></p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>by Prefect 0.5.0 on March 29, 2019 at 17:39 UTC</p>