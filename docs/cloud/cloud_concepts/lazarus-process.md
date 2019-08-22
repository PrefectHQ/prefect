# Lazarus Process

The Lazarus process is responsible for rescheduling any submitted or running flow runs without
corresponding submitted or running task runs.

## How is this useful?

The Lazarus process is meant to gracefully retry failures caused by factors outside of Prefect's
control. The most common situations requiring Lazarus intervention are infrastructure issues, such
as Kubernetes pods not spinning up or being deleted before they're able to complete a run.

## How does this work?

Once every 10 minutes, the Lazarus process searches for distressed flow runs. Each flow run found
in this manner is rescheduled; this intervention by Lazarus is reflected in the flow run's logs.

Where necessary, flow runs without submitted or running task runs will be rescheduled by the Lazarus
process up to 10 times. Should the Lazarus process attempt to reschedule a flow run for the eleventh
time, it will be marked failed instead.
