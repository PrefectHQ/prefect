---
sidebarDepth: 2
editLink: false
---
# Artifacts

::: warning Experimental
<div class="experimental-warning">
<svg
    aria-hidden="true"
    focusable="false"
    role="img"
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 448 512"
    >
<path
fill="#e90"
d="M437.2 403.5L320 215V64h8c13.3 0 24-10.7 24-24V24c0-13.3-10.7-24-24-24H120c-13.3 0-24 10.7-24 24v16c0 13.3 10.7 24 24 24h8v151L10.8 403.5C-18.5 450.6 15.3 512 70.9 512h306.2c55.7 0 89.4-61.5 60.1-108.5zM137.9 320l48.2-77.6c3.7-5.2 5.8-11.6 5.8-18.4V64h64v160c0 6.9 2.2 13.2 5.8 18.4l48.2 77.6h-172z"
>
</path>
</svg>

<div>
The functionality here is experimental, and may change between versions without notice. Use at your own risk.
</div>
</div>
:::

---


## Functions
|top-level functions: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-artifacts-create-link'><p class="prefect-class">prefect.artifacts.create_link</p>(link)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/artifacts.py#L40">[source]</a></span></div>
<p class="methods">Create a link artifact<br><br>**Args**:     <ul class="args"><li class="args">`link (str)`: the link to post</li></ul> **Returns**:     <ul class="args"><li class="args">`str`: the task run artifact ID</li></ul></p>|
 | <div class='method-sig' id='prefect-artifacts-update-link'><p class="prefect-class">prefect.artifacts.update_link</p>(task_run_artifact_id, link)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/artifacts.py#L55">[source]</a></span></div>
<p class="methods">Update an existing link artifact. This function will replace the current link artifact with the new link provided.<br><br>**Args**:     <ul class="args"><li class="args">`task_run_artifact_id (str)`: the ID of an existing task run artifact     </li><li class="args">`link (str)`: the new link to update the artifact with</li></ul></p>|
 | <div class='method-sig' id='prefect-artifacts-create-markdown'><p class="prefect-class">prefect.artifacts.create_markdown</p>(markdown)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/artifacts.py#L73">[source]</a></span></div>
<p class="methods">Create a markdown artifact<br><br>**Args**:     <ul class="args"><li class="args">`markdown (str)`: the markdown to post</li></ul> **Returns**:     <ul class="args"><li class="args">`str`: the task run artifact ID</li></ul></p>|
 | <div class='method-sig' id='prefect-artifacts-update-markdown'><p class="prefect-class">prefect.artifacts.update_markdown</p>(task_run_artifact_id, markdown)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/artifacts.py#L88">[source]</a></span></div>
<p class="methods">Update an existing markdown artifact. This function will replace the current markdown artifact with the new markdown provided.<br><br>**Args**:     <ul class="args"><li class="args">`task_run_artifact_id (str)`: the ID of an existing task run artifact     </li><li class="args">`markdown (str)`: the new markdown to update the artifact with</li></ul></p>|
 | <div class='method-sig' id='prefect-artifacts-delete-artifact'><p class="prefect-class">prefect.artifacts.delete_artifact</p>(task_run_artifact_id)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/artifacts.py#L106">[source]</a></span></div>
<p class="methods">Delete an existing artifact<br><br>**Args**:     <ul class="args"><li class="args">`task_run_artifact_id (str)`: the ID of an existing task run artifact</li></ul></p>|

<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on July 1, 2021 at 18:35 UTC</p>