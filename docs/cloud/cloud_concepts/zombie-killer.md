# Zombie Killer

The zombie killer process is responsible for handling zombies, tasks that claim to be running
but haven't updated their heartbeat in the past 10 minutes. The zombie killer marks zombies
and their parent flows as failed.

Runs marked as failed by the zombie killer process with have `Marked "Failed" by a Zombie Killer process`
written to their logs.
