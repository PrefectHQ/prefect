# Services

The Prefect platform runs a variety of automatic services to ensure workflow semantics are respected robustly.

## Scheduler

The `Scheduler` service is responsible for scheduling new flow runs.

### How is it useful?

In many distributed systems, the scheduler is a single point of failure. Our API was designed to have a robust, asynchronous scheduling service whose only job is to correctly generate future flow runs. It can be trivially restarted or even run concurrently without issue.

More importantly, the scheduler service is not responsible for actually running flows -- that's what [Agents](/orchestration/agents/overview) are for. This means that scheduled runs can happily coexist with manually-started runs; Agents are indifferent to _how_ a run was created. You can tell if a run was created by the Scheduler service because it will have an `auto_scheduled` flag set to `TRUE`. Manually-created runs will record the user that created them.

### How does it work?

The scheduler periodically queries for flows with active schedules and creates flow runs corresponding to the next 10 scheduled start times of the flow. Therefore, to disable scheduling, simply toggle your flow's schedule to `PAUSED`, and reactivate it whenever you want scheduling to resume.

If you pause a schedule, any future auto-scheduled runs that have not started will be deleted. Reactivating the schedule will cause them to be recreated, as long as they are scheduled to start in the future. The scheduler will never create runs that were scheduled to start in the past.

## Lazarus

The `Lazarus` process is responsible for rescheduling any submitted or running flow runs without
corresponding submitted or running task runs.

### How is it useful?

The Lazarus process is meant to gracefully retry failures caused by factors outside of Prefect's control. The most common situations requiring Lazarus intervention are infrastructure issues, such as Kubernetes pods not spinning up or being deleted before they're able to complete a run.

### How does it work?

Once every 10 minutes, the Lazarus process searches for distressed flow runs. Each flow run found in this manner is rescheduled; this intervention by Lazarus is reflected in the flow run's logs.

Where necessary, flow runs without submitted or running task runs will be rescheduled by the Lazarus process up to 10 times. Should the Lazarus process attempt to reschedule a flow run for the eleventh time, it will be marked failed instead.

## Zombie Killer

The `Zombie Killer` service is responsible for handling zombies, which Prefect defines as tasks that claim to be running but haven't updated their heartbeat in the past 2 minutes (Prefect Cloud) or 10 minutes (Prefect Server).

### How is it useful?

Zombies are tasks that started running but -- for some reason -- are no longer in communication with the API. Since Prefect is usually able to capture errors in code, the most common reason for a zombie is an unexpected infrastructure event in the execution cluster: a node failure, loss of internet, or other catastrophic error. Zombie tasks prevent flow progress: downstream tasks won't start while they believe an upstream dependency is running. Therefore, when the Zombie Killer detects a zombie, it marks the task failed so that execution can continue.

### How does it work?

Periodically, the Zombie Killer queries for tasks that are in a `Running` state but have no recent heartbeat. These tasks are placed into a `Failed` state with the message `Marked "Failed" by a Zombie Killer process`. If the flow is in a `Running` state, the [Lazarus](#lazarus) process will ensure it resumes execution.

### Heartbeat configuration

It's possible for the system kernel to terminate the heartbeat process prematurely and trigger the `Zombie Killer`. To circumvent this, try configuring `Prefect` to run the heartbeat in a thread.

The heartbeat can be configured by adding a line to `config.toml` in the `[cloud]` section
```
[cloud]
heartbeat_mode = "thread" # ['process', 'thread', 'off']
```

Additionally, this can be set using the `run_config`
```python
from prefect.run_configs import UniversalRun
flow.run_config = UniversalRun(env={"PREFECT__CLOUD__HEARTBEAT_MODE": "thread"})
```

## Towel

The `Towel` service is an orchestration layer for maintenance routines that are critical to Prefect's operation, including some of the services on this page.

### How is it useful?

> A towel, The Hitchhiker's Guide to the Galaxy says, is about the most massively useful thing an interstellar hitchhiker can have. Partly it has great practical value. You can wrap it around you for warmth as you bound across the cold moons of Jaglan Beta; you can lie on it on the brilliant marble-sanded beaches of Santraginus V, inhaling the heady sea vapours; you can sleep under it beneath the stars which shine so redly on the desert world of Kakrafoon; use it to sail a miniraft down the slow heavy River Moth; wet it for use in hand-to-hand-combat; wrap it round your head to ward off noxious fumes or avoid the gaze of the Ravenous Bugblatter Beast of Traal (such a mind-bogglingly stupid animal, it assumes that if you can't see it, it can't see you — daft as a brush, but very very ravenous); you can wave your towel in emergencies as a distress signal, and of course dry yourself off with it if it still seems to be clean enough.

### How does it work?

> More importantly, a towel has immense psychological value. For some reason, if a strag (strag: non-hitch hiker) discovers that a hitchhiker has his towel with him, he will automatically assume that he is also in possession of a toothbrush, face flannel, soap, tin of biscuits, flask, compass, map, ball of string, gnat spray, wet weather gear, space suit etc., etc. Furthermore, the strag will then happily lend the hitch hiker any of these or a dozen other items that the hitch hiker might accidentally have "lost." What the strag will think is that any man who can hitch the length and breadth of the galaxy, rough it, slum it, struggle against terrible odds, win through, and still knows where his towel is, is clearly a man to be reckoned with.
