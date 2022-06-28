# Flow Run

## Overview

![](/orchestration/ui/flowrun-overview.png)

## Creation

To create a flow run from the UI, visit the [flow page](/orchestration/ui/flow.html#run) and click "Run Flow".

![](/orchestration/ui/flow-run.png)

## Schematic

The schematic is an interactive, live-updating look at the progress of each run. As tasks go through different states, their colors and state messages update accordingly.

![](/orchestration/ui/flowrun-schematic.png)

## Logs

The logs page shows live-updating logs from the flow run. They may be filtered, queried, and downloaded for convenience.
![](/orchestration/ui/flowrun-logs.png)

## Restarting

To manually restart a run from any failed tasks, click the "Restart" button in the action bar.

If you want to restart the run from a specific task, visit the corresponding [task run page](/orchestration/ui/task-run) and click "Restart" on that page.

!!! warning Results
    The confirmation box notes that if your failed tasks require data from upstream tasks, and you did not specify a result to serialize that data, then your retry will fail. This is because without the upstream data, there's no way for your tasks to run. All Prefect `Storage` classes except `Docker` have default `Result` subclasses; if your flow runs in a Docker container you will need to specify a result subclass when you register your flow for this feature to work.

![](/orchestration/ui/flowrun-restart.png)

## Updating State

To manually update a flow run's state, click the "Mark As" button in the action bar. This will bring up a modal allowing you to specify a new state for the run.
![](/orchestration/ui/flowrun-mark-as.png)
