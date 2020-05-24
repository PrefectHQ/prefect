# Flow

## Overview

The flow overview summarizes each flow's recent behavior. It is a dashboard for a single workflow.
![](/orchestration/ui/flow-overview.png)

## Schematic

The flow schematic shows an interactive overview of all the tasks in the flow and their dependency structure.
![](/orchestration/ui/flow-schematic.png)

## Versions

The "versions" page shows a history of all versions of this flow.
![](/orchestration/ui/flow-versions.png)

## Run

From this page, you can schedule a new run of your flow. You may provide parameter values, if appropriate, and give your run a name for easy queries or retrieval in the future.
![](/orchestration/ui/flow-run.png)

## Settings <Badge text="Cloud"/>

You can use the settings page to change which project your flow is part of and toggle [flow settings](/orchestration/concepts/flows.html#flow-settings) such as heartbeat, Lazarus process and version locking. You can also use the page to set [Cloud Hooks](/orchestration/concepts/cloud_hooks.html). 

<div class="add-shadow">
  <img src="/orchestration/ui/flow-settings.png">
</div>

<style>
.add-shadow  {
    width: 100%;
    height: auto;
    vertical-align: bottom;
    z-index: -1;
    outline: 1;
    box-shadow: 0px 20px 15px #3D4849;
}
</style>