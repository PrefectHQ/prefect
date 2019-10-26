---
sidebarDepth: 2
editLink: false
---
# Dropbox Tasks
---
Tasks that interface with Dropbox.

Tasks in this collection require a Prefect Secret called `"DROPBOX_ACCESS_TOKEN"` that contains
a valid Dropbox access token.
 ## DropboxDownload
 <div class='class-sig' id='prefect-tasks-dropbox-dropbox-dropboxdownload'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.dropbox.dropbox.DropboxDownload</p>(path=None, access_token_secret=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/dropbox/dropbox.py#L8">[source]</a></span></div>

Task for downloading a file from Dropbox. Note that _all_ initialization settings can be provided / overwritten at runtime.

**Args**:     <ul class="args"><li class="args">`path (str, optional)`: the path to the file to download. May be provided at runtime.     </li><li class="args">`access_token_secret (str, optional)`: the name of the Prefect Secret containing a         Dropbox access token; defaults to `"DROPBOX_ACCESS_TOKEN"`     </li><li class="args">`**kwargs (optional)`: additional kwargs to pass to the `Task` constructor</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-dropbox-dropbox-dropboxdownload-run'><p class="prefect-class">prefect.tasks.dropbox.dropbox.DropboxDownload.run</p>(path=None, access_token_secret=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/dropbox/dropbox.py#L25">[source]</a></span></div>
<p class="methods">Run method for this Task.  Invoked by _calling_ this Task within a Flow context, after initialization.<br><br>**Args**:     <ul class="args"><li class="args">`path (str, optional)`: the path to the file to download     </li><li class="args">`access_token_secret (str, optional)`: the name of the Prefect Secret containing a         Dropbox access token; defaults to `"DROPBOX_ACCESS_TOKEN"`</li></ul>**Raises**:     <ul class="args"><li class="args">`ValueError`: if the `path` is `None`</li></ul>**Returns**:     <ul class="args"><li class="args">`bytes`: the file contents, as bytes</li></ul></p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on October 17, 2019 at 13:42 UTC</p>