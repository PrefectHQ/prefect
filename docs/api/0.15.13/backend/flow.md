---
sidebarDepth: 2
editLink: false
---
# Flow

!!! warning Experimental
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

 ## FlowView
 <div class='class-sig' id='prefect-backend-flow-flowview'><p class="prefect-sig">class </p><p class="prefect-class">prefect.backend.flow.FlowView</p>(flow_id, settings, run_config, serialized_flow, archived, project_name, core_version, storage, name, flow_group_labels)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/backend/flow.py#L19">[source]</a></span></div>

A view of Flow metadata stored in the Prefect API.

This object is designed to be an immutable view of the data stored in the Prefect backend API at the time it is created

EXPERIMENTAL: This interface is experimental and subject to change

**Args**:     <ul class="args"><li class="args">`flow_id`: The uuid of the flow     </li><li class="args">`settings`: A dict of flow settings     </li><li class="args">`run_config`: A dict representation of the flow's run configuration     </li><li class="args">`serialized_flow`: A serialized copy of the flow     </li><li class="args">`archived`: A bool indicating if this flow is archived or not     </li><li class="args">`project_name`: The name of the project the flow is registered to     </li><li class="args">`core_version`: The core version that was used to register the flow     </li><li class="args">`storage`: The deserialized Storage object used to store this flow     </li><li class="args">`name`: The name of the flow     </li><li class="args">`flow_group_labels`: Labels that are assigned to the parent flow group</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-backend-flow-flowview-from-flow-group-id'><p class="prefect-class">prefect.backend.flow.FlowView.from_flow_group_id</p>(flow_group_id)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/backend/flow.py#L155">[source]</a></span></div>
<p class="methods">Get an instance of this class given a `flow_group_id` to lookup; the newest flow in the flow group will be retrieved<br><br>**Args**:     <ul class="args"><li class="args">`flow_group_id`: The uuid of the flow group</li></ul> **Returns**:     A new instance of FlowView</p>|
 | <div class='method-sig' id='prefect-backend-flow-flowview-from-flow-id'><p class="prefect-class">prefect.backend.flow.FlowView.from_flow_id</p>(flow_id)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/backend/flow.py#L137">[source]</a></span></div>
<p class="methods">Get an instance of this class given a `flow_id` to lookup<br><br>**Args**:     <ul class="args"><li class="args">`flow_id`: The uuid of the flow</li></ul> **Returns**:     A new instance of FlowView</p>|
 | <div class='method-sig' id='prefect-backend-flow-flowview-from-flow-name'><p class="prefect-class">prefect.backend.flow.FlowView.from_flow_name</p>(flow_name, project_name=&quot;&quot;, last_updated=False)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/backend/flow.py#L181">[source]</a></span></div>
<p class="methods">Get an instance of this class given a flow name. Optionally, a project name can be included since flow names are not guaranteed to be unique across projects.<br><br>**Args**:     <ul class="args"><li class="args">`flow_name`: The name of the flow to lookup     </li><li class="args">`project_name`: The name of the project to lookup. If `None`, flows with an         explicitly null project will be searched. If `""` (default), the         lookup will be across all projects.     </li><li class="args">`last_updated`: By default, if multiple flows are found an error will be         thrown. If `True`, the most recently updated flow will be returned         instead.</li></ul> **Returns**:     A new instance of FlowView</p>|
 | <div class='method-sig' id='prefect-backend-flow-flowview-from-id'><p class="prefect-class">prefect.backend.flow.FlowView.from_id</p>(flow_id)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/backend/flow.py#L106">[source]</a></span></div>
<p class="methods">Get an instance of this class given a `flow_id` or `flow_group_id` to lookup. The `flow_id` will be tried first.<br><br>**Args**:     <ul class="args"><li class="args">`flow_id`: The uuid of the flow or the flow group</li></ul> **Returns**:     A new instance of FlowView</p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on February 23, 2022 at 19:26 UTC</p>