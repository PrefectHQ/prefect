---
description: Users - special features for Prefect Cloud users
tags:
    - Prefect Cloud
    - Users
---

# Users

Reuter drafting

Some content taken from old ui/flow-run page if we want it:

## Flow run retention policy

!!! info "Prefect Cloud feature"
    The Flow Run Retention Policy setting is only applicable in Prefect Cloud.

Flow runs in Prefect Cloud are retained according to the Flow Run Retention Policy setting in your personal account or organization profile. The policy setting applies to all workspaces owned by the personal account or organization respectively. 

The flow run retention policy represents the number of days each flow run is available in the Prefect Cloud UI, and via the Prefect CLI and API after it ends. Once a flow run reaches a terminal state ([detailed in the chart here](/concepts/states/#state-types)), it will be retained until the end of the flow run retention period. 

!!! tip "Flow Run Retention Policy keys on terminal state"
    Note that, because Flow Run Retention Policy keys on terminal state, if two flows start at the same time, but reach a terminal state at different times, they will be removed at different times according to when they each reached their respective terminal states.

This retention policy applies to all [details about a flow run](/ui/flow-runs/#inspect-a-flow-run), including its task runs. Subflow runs follow the retention policy independently from their parent flow runs, and are removed based on the time each subflow run reaches a terminal state. 

If you or your organization have needs that require a tailored retention period, [contact our Sales team](https://www.prefect.io/pricing).