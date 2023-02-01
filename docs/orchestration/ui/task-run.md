# Task Run

<div style="border: 2px solid #27b1ff; border-radius: 10px; padding: 1em;">
Looking for the latest <a href="https://docs.prefect.io/">Prefect 2</a> release? Prefect 2 and <a href="https://app.prefect.cloud">Prefect Cloud 2</a> have been released for General Availability. See <a href="https://docs.prefect.io/">https://docs.prefect.io/</a> for details.
</div>

## Overview

The task run schematic is an interactive, live-updating look at the progress of this task run and its immediate neighbors. As tasks go through different states, their colors and state messages update accordingly.

![](/orchestration/ui/taskrun-overview.png)

## Logs

The logs page shows live-updating logs from the task run. They may be filtered, queried, and downloaded for convenience.
![](/orchestration/ui/taskrun-logs.png)

## Restarting

To manually restart a flow run from this task, click the "Restart" button in the action bar.

![](/orchestration/ui/taskrun-restart.png)

## Updating State

To manually update a task run's state, click the "Mark As" button in the action bar. This will bring up a modal allowing you to specify a new state for the run.
![](/orchestration/ui/taskrun-mark-as.png)
