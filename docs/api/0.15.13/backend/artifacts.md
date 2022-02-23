---
sidebarDepth: 2
editLink: false
---
# Artifacts
---

## Functions
|top-level functions: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-backend-artifacts-create-link-artifact'><p class="prefect-class">prefect.backend.artifacts.create_link_artifact</p>(link)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/backend/artifacts.py#L40">[source]</a></span></div>
<p class="methods">Create a link artifact<br><br>**Args**:     <ul class="args"><li class="args">`link (str)`: the link to post</li></ul> **Returns**:     <ul class="args"><li class="args">`str`: the task run artifact ID</li></ul></p>|
 | <div class='method-sig' id='prefect-backend-artifacts-update-link-artifact'><p class="prefect-class">prefect.backend.artifacts.update_link_artifact</p>(task_run_artifact_id, link)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/backend/artifacts.py#L55">[source]</a></span></div>
<p class="methods">Update an existing link artifact. This function will replace the current link artifact with the new link provided.<br><br>**Args**:     <ul class="args"><li class="args">`task_run_artifact_id (str)`: the ID of an existing task run artifact     </li><li class="args">`link (str)`: the new link to update the artifact with</li></ul></p>|
 | <div class='method-sig' id='prefect-backend-artifacts-create-markdown-artifact'><p class="prefect-class">prefect.backend.artifacts.create_markdown_artifact</p>(markdown)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/backend/artifacts.py#L73">[source]</a></span></div>
<p class="methods">Create a markdown artifact<br><br>**Args**:     <ul class="args"><li class="args">`markdown (str)`: the markdown to post</li></ul> **Returns**:     <ul class="args"><li class="args">`str`: the task run artifact ID</li></ul></p>|
 | <div class='method-sig' id='prefect-backend-artifacts-update-markdown-artifact'><p class="prefect-class">prefect.backend.artifacts.update_markdown_artifact</p>(task_run_artifact_id, markdown)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/backend/artifacts.py#L88">[source]</a></span></div>
<p class="methods">Update an existing markdown artifact. This function will replace the current markdown artifact with the new markdown provided.<br><br>**Args**:     <ul class="args"><li class="args">`task_run_artifact_id (str)`: the ID of an existing task run artifact     </li><li class="args">`markdown (str)`: the new markdown to update the artifact with</li></ul></p>|
 | <div class='method-sig' id='prefect-backend-artifacts-delete-artifact'><p class="prefect-class">prefect.backend.artifacts.delete_artifact</p>(task_run_artifact_id)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/backend/artifacts.py#L106">[source]</a></span></div>
<p class="methods">Delete an existing artifact<br><br>**Args**:     <ul class="args"><li class="args">`task_run_artifact_id (str)`: the ID of an existing task run artifact</li></ul></p>|

<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on February 23, 2022 at 19:26 UTC</p>