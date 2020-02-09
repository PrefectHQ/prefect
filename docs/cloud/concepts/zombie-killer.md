# Zombie Killer

The zombie killer process is responsible for handling zombies, which Prefect defines as tasks that claim to be running
but haven't updated their heartbeat in the past 2 minutes.  Tasks in this state began running but died at some point -
because Prefect maintains a strict run-once rule for Tasks, the zombie killer marks zombies
and their parent flows as failed.

Runs marked as failed by the zombie killer process will have `Marked "Failed" by a Zombie Killer process`
written to their logs.
