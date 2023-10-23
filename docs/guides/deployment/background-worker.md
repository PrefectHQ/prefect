---
description: Learn how to set up a systemd service to daemonize a Prefect worker
tags:
    - systemd
    - daemonize
    - worker
search:
  boost: 2
---


This post demonstrates how to set up a systemd service to run a Prefect worker.

A systemd service is an ideal way to run a Prefect worker on a Linux VM or physical server if you want to:

* Automatically start a Prefect worker when Linux starts.
* Automatically restart a Prefect worker if it crashes.

In this guide you will:

* Create a Linux user
* Install Prefect
* Set up a systemd service for the Prefect worker

# Prerequisites

Here's what you'll need before proceeding:

* An environment with a linux operating system with [systemd](https://systemd.io/) and Python 3.8 or later.
* A superuser account (you can run `sudo` commands).
* A Prefect Cloud account, or a local instance of a Prefect server running on your network.
* A Prefect [deployment](/concepts/deployments/) with a [work pool](/concepts/work-pools/) your worker can connect to.

## Add a user

First, create a user account on your linux system for the Prefect worker.
While you can run the worker as root, it's good security practice to avoid doing so unless you are sure you need to.

In a terminal, run:

```bash
sudo useradd -m prefect
sudo passwd prefect
```

When prompted, enter a password for the `prefect` account.

Next, log in to the `prefect` account by running:

```
sudo su prefect
```

## Install Prefect

Run:

```
pip install prefect
```

This assumes you are installing Prefect globally, not in a virtual environment.
If running a systemd service in a virtual environment, you'll just need to change the ExecPath.
For example, if using [venv](https://docs.python.org/3/library/venv.html), change the ExecPath to target the `prefect` application in the `bin` subdirectory of your virtual environment.

Next, set up your environment so that the Prefect client will know which server to connect to.

=== "Prefect Cloud"

If connecting to Prefect Cloud, follow [the instructions](https://docs.prefect.io/ui/cloud-getting-started/#create-an-api-key) to obtain an API key and then run:

```
prefect cloud login -k YOUR_API_KEY
```

When prompted, choose the Prefect workspace you'd like to log in to.

=== "Prefect server instance"

If connecting to a local Prefect server instance, run the following and substitute the IP address of your server:

```
prefect config set PREFECT_API_URL=http://your-prefect-server-IP:4200
```

Finally, run the `exit` command to sign out of the `prefect` Linux account.
This command switches you back to your sudo-enabled account so you will can run the commands in the next section.

## Set up a systemd service for the Prefect worker

You can set up your Prefect worker and systemd service with a text editor. Below, we use Vim:

```bash
cd /etc/systemd/system
sudo vim prefect-worker.service
```

Add the following lines to the file:

```
[Unit]
Description=Prefect Worker

[Service]
User=prefect
WorkingDirectory=/home/prefect
ExecStart=/usr/local/bin/prefect worker start --pool YOUR_WORK_POOL_NAME
Restart=always

[Install]
WantedBy=multi-user.target

```

Make sure you substitute your own work pool name.
Save the file and exit.
To exit vim hit the escape key, type `:wq!`, then press the return key.

Next, run `systemctl daemon-reload` to make systemd aware of your new service.

Then, run `systemctl enable prefect-worker` to enable the service.
This command will ensure it runs when your system boots.

Finally, run `systemctl start prefect-worker` to start the service.
And that's it! You now have a systemd service that starts a Prefect worker when your system boots, and will restart the worker if it ever crashes.

## Next steps

If you want to run a worker on a Windows machine the pattern is similar.
Instead of systemd, you will want to use [NSSM](https://nssm.cc/).

To run a worker in Kubernetes using Helm see [the Kubernetes guide](/guides/deployment/kubernetes/#deploy-a-worker-using-helm).

To run your workflows on serverless cloud infrastructure, no worker is required if you use a push work pool with Prefect Cloud. See [the guide](/guides/deployment/push-work-pools/) to learn more.
