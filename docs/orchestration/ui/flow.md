# Flow

## Overview

The flow overview summarizes each flow's recent behavior. It is a dashboard for a single workflow.

In the details tile of the flow overview, you can add and remove flow group labels.  As with other [flow group settings](/orchestration/ui/flow.html#flow-group-settings), these flow group labels take precedence over the labels your flow is registered with. 


<div class="add-shadow">
  <img src="/orchestration/ui/flow-overview.png">
</div>

## Schematic

The flow schematic shows an interactive overview of all the tasks in the flow and their dependency structure.
![](/orchestration/ui/flow-schematic.png)

## Read Me

You can use markdown to add a Read Me description for your flow group in the flow Read Me tab.  When you update the Read Me in the UI, it updates the description for all versions of your flow.  

<div class="add-shadow">
  <img src="/orchestration/ui/flow-description.png">
</div>


<div class="add-shadow">
  <img src="/orchestration/ui/flow-description-edit.png">
</div>

## Run

From this page, you can schedule a new run of your flow for now or some point in the future.

You can also customize the new run of your flow, including:
- Providing parameter values
- Updating your run configuration
- Specifying logging level
- Customizing your run name for easy queries or retrieval in the future

<div class="add-shadow">
  <img src="/orchestration/ui/flow-run.png">
</div>

## Settings

You can use the settings page to change which project your flow is part of and toggle [flow settings](/orchestration/concepts/flows.html#flow-settings) such as heartbeat, Lazarus process and version locking. You can also use the page to set [Cloud Hooks](/orchestration/concepts/cloud_hooks.html), [Schedules](/core/concepts/schedules.html), and [Parameters](/core/concepts/parameters.html).  

When you update schedules and parameters in the settings pages of the UI, it updates the settings for all versions of that flow, otherwise known as its flow group settings.

<div class="add-shadow">
  <img src="/orchestration/ui/flow-settings.png">
</div>


## Flow Group Settings

A flow group setting overrides individual flow settings. They supersede any re-registrations of your flow and act as the source of truth until they are removed. 

For example if you update flow group parameters via the UI (or GraphQL), those parameters will take precedence over the parameters your flow is registered with. 

<div class="add-shadow">
  <img src="/orchestration/ui/flow-group-settings.png">
</div>


<style>
.add-shadow  {
    width: 100%;
    height: auto;
    vertical-align: bottom;
    z-index: -1;
    outline: 1;
    box-shadow: 0px 20px 15px #3D4849;
    margin-bottom: 50px
}
</style>
