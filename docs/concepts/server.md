---
description: Prefect Sever
tags:
    - UI
    - dashboard
    - Prefect Cloud
    - Observability
    - Events
---

# Prefect Server

Once you've installed Prefect you have a Python SDK client that can communicate with [Prefect Cloud](https://app.prefect.cloud), the platform hosted by Prefect. At the same time you've also installed an [API server]() backed by a database and a UI. The [database]() is a SQLite database by default, but a PostgreSQL database can be used instead.

TK screenshot of Prefect Server UI.

Spin up a local Prefect server UI with the `prefect server start` CLI command in the terminal:

<div class="terminal">
```bash
$ prefect server start
```
</div>

Open the URL for the Prefect server UI ([http://127.0.0.1:4200](http://127.0.0.1:4200) by default) in a browser. 

![Viewing the orchestrated flow runs in the Prefect UI.](../img/tutorials/first-steps-ui.png)

