---
title: Welcome
sidebarDepth: 0
---

<div align="center" style="margin-top:50px; margin-bottom:40px;">
    <img src="/illustrations/cloud-illustration.svg"  width=300 >
</div>

# Orchestration

When you want to run and monitor many flows, maintaining their state and inspecting their progress can be difficult without some extra tooling.

Prefect Cloud and the Prefect Core server and are two ready-to-use state database and UI backends that automatically extend the Prefect Core engine with a rich GraphQL API to make orchestration of your flows easy.

Prefect Core's server is an open source, lightweight version of our highly-available, production-ready product Prefect Cloud.

Most users get the greatest benefit from signing up for the [free Prefect Cloud Starter tier](https://cloud.prefect.io/), which supports up to 3 users and 10,000 free runs every month. 

If your team needs support for additional users, automations, multi-tenant permissions, SSO, and other features, [scale up to a bigger Prefect Cloud license](https://www.prefect.io/pricing/). 

Prefect Core also includes an open source, locally hosted server.

All of your Prefect flows will work seamlessly on any of these backends, so you won't need to change any of your flow code to change between them.

### Prefect Cloud

Prefect Cloud is a fully hosted, production-ready backend for Prefect Core that provides enhanced features for flow orchestration and visibility, including:

- A hosted web UI for running and monitoring flows and jobs
- Automatic and asynchronous scheduling and alerting
- Permissions and authorization management
- Performance enhancements that allow you to scale
- Agent monitoring
- Secure runtime secrets and parameters
- Team management
- SLAs
- A full GraphQL API
- Many more features...

In the Prefect documentation, the <Badge text="Cloud"/> badge indicates features supported only in Prefect Cloud.

To start monitoring and managing your flows in Prefect cloud, [log in or sign up](https://universal.prefect.io) today.

### Prefect Core server

Prefect Core ships with an open-source backend and UI that automatically extends the Prefect Core engine with a subset of the features provided by Prefect Cloud, including:

- A local web UI for running and monitoring flows and jobs
- A full GraphQL API
- Automatic and asynchronous scheduling and alerting

We recommend Prefect Core server for local testing and environments with restricted access to cloud services.

Get started by running `prefect server start` and navigate to `http://localhost:8080`.

**Note:** Prefect Server requires both Docker and Docker Compose.

## Architecture Overview

Prefect's unique [hybrid execution model](https://medium.com/the-prefect-blog/the-prefect-hybrid-model-1b70c7fd296) keeps your code and data completely private while taking full advantage of our managed orchestration service.

<div align="center" style="margin-top:30px; margin-bottom:30px;">
    <img src="/prefect_architecture_overview.png" >
</div>

When you register a [Flow](https://docs.prefect.io/core/concepts/flows.html), your code is securely stored on your infrastructure &mdash; your code never leaves your execution environment and is never sent to Prefect Cloud. Instead, Flow metadata is sent to Prefect Cloud for scheduling and orchestration.

Prefect [Agents](https://docs.prefect.io/orchestration/agents/overview.html) run inside a user's architecture, and are responsible for starting and monitoring flow runs. Agents send requests to the Prefect Cloud API to update flow run metadata.

Prefect Cloud's live updating [UI](https://docs.prefect.io/orchestration/ui/dashboard.html#overview) allows you to monitor flow execution in real time and leverage Prefect Cloud's extensive integration functionality.

We know one of these solutions will minimize your [negative engineering](https://medium.com/the-prefect-blog/positive-and-negative-data-engineering-a02cb497583d) burden and get you back to the code you really want to write.

Happy engineering!

_- The Prefect Team_
