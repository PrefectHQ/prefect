---
sidebarDepth: 1
---

# Server Overview


[[toc]]


## What is Prefect Server?

Prefect Server is an open source backend that makes it easy to monitor and execute your Prefect flows. 
Under the hood, Prefect Server is actually [a diverse collection of services](architecture.html) that provide a persistent record of your runs, current state, and allow for asynchronous scheduling and notifications.
It was designed to expose many of the popular developer features of Prefect Cloud in a way that allows for community contributions, collaborations and customizations.  In particular, Prefect Server ships out-of-the-box with:

- A persistent metadata database
- A highly scalable scheduler 
- An expressive GraphQL API for making queries and triggering actions (e.g., event-driven flow runs)
- A unique design that separates the host processes from execution processes so that you can schedule and orchestrate Flows with diverse execution environments
- Services that ensure your Flows succeed or at least [fail successfully](https://medium.com/the-prefect-blog/positive-and-negative-data-engineering-a02cb497583d)
- A fully featured User Interface (UI) 

Development of Prefect Server is fully open-source, the code exists across two repositories:

- [Prefect Server](https://github.com/PrefectHQ/Server): code for all services running in
  Prefect Server
- [Prefect UI](https://github.com/PrefectHQ/ui) code for the UI running in both Prefect Server
  _and_ Prefect Cloud

If you have feature requests or run into problems, please file an issue in the appropriate
repository.

## Deploying Prefect Server

Prefect Server is designed to be deployed inside user infrastructure, and should be runnable in a wide
variety of deployment backends. 

For deployment instructions, read our guide to [Single-Node Deployment](/orchestration/Server/deploy-local.html) or, if you have a Kubernetes cluster you'd prefer to use, see the [Helm chart README](https://github.com/PrefectHQ/server/tree/master/helm/prefect-server).

!!! warning Migrating off of Prefect Server <= 0.12.6
    The initial release of Prefect Server with Prefect Core 0.12.6 is no longer supported. Due to the large number of features and changes in the new [Server codebase](https://github.com/PrefectHQ/server) there is unfortunately no route to migrating your run and state history to a new Server installation.
:::

!!! warning Docker and Docker Compose required
    Because of [the diverse collection of services required](architecture.html) to run the full backend, Prefect Server ships as a docker-compose file that allows each of these services to run inside a custom configured Docker image within an appropriately configured Docker network.  This allows users to get up and running with a single CLI command. docker-compose is not included in our Python requirements file as it is not necessary for general use of Prefect. We require a minimum docker-compose version of `1.18.0`.
:::

## Prefect Server vs. Prefect Cloud - which should I choose?

Prefect Server and Prefect Cloud share many similarities - in fact, some of the Server services run almost unchanged in Prefect Cloud! Despite this, there are some differences (outlined below) that are worth considering in your decision. Because Prefect Cloud is built _on top of_ Prefect Server's codebase, we will focus entirely on the additional benefits of Cloud over Server.

!!! tip On-prem security either way
    Because of [Prefect's innovative Hybrid Model](https://medium.com/the-prefect-blog/the-prefect-hybrid-model-1b70c7fd296), both your code and proprietary data remain safe within your infrastructure and control regardless of which offering you choose.
:::

### Authorization and Permissions

Prefect Cloud supports users as a first-class concept, which allows for:
- Permissioned access to the UI through [Auth0](https://auth0.com/)
- [Customizable access controls](/orchestration/rbac/overview.html)
- An authenticated GraphQL API that can only be accessed via special API keys
- A full team management experience

### API network accessibility and custom deployments

Because Prefect Cloud's API is accessible from any location with access to `api.prefect.io`, it is much easier to customize your flow deployments and developer workflows without the hassle of maintaining a network endpoint. From registering flows with your favorite CI/CD tool to running multiple Agents across different clusters and machines, all you need to ensure is that your tools and services have an appropriately permissioned Cloud API key.

### Enterprise features

In addition to user roles and authorization, Prefect Cloud ships with many additional features that are commonly required for business critical deployments:
- An SLA service for configuring special alerts
- Single Sign-On (SSO) integrations
- Agent monitoring
- Special types of Cloud Hooks for notifications
- An audit trail of all tenant activity
- High Availability
- [Enterprise Support](#support) (see below)
- Secure runtime secrets

### Scale & Performance

Prefect Cloud was designed with scale and performance in mind.  Depending on the volume of work you routinely run, you will likely notice a stark difference between Server flow runs and Cloud flow runs.  In particular, we have observed that ~10-20 tasks running concurrently against a typical Server deployments could be as much as 3x faster when run with Cloud.  This difference is magnified as you scale up: once you are running ~50-100 tasks concurrently the difference in speed can be as large as 6x.  Ultimately these differences boil down to API responsiveness, and consequently UI performance is also directly affected.

### Support

Various support tiers are available to Prefect Cloud customers, ranging from dedicated consulting hours to shared Slack channels.  Premium support is not offered for Prefect Server.

For more details, please [contact us](mailto:hello@prefect.io).
