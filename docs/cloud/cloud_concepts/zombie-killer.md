# Zombie Killer

The Zombie Killer process is responsible for handling zombie tasks, tasks that claim to be running
but haven't updated their heartbeat in the past 10 minutes. The zombie killer marks zombie tasks
and their parent flows as failed, allowing written logic or users to proceed as desired.
