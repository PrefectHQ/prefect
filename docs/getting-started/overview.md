---
description: Welcome to Prefect 2!
tags:
    - overview
    - quick start
    - resources
---

# Getting Started

Welcome to Prefect!  

Whether you've been working with Prefect for years or this is your first time, this collection of tutorials will guide you through the process of defining, running, monitoring and eventually automating your first Prefect 2 workflow.  

First and foremost, you'll need [a working version of Prefect 2 installed](installation.md).  

From there, you can [follow along with the tutorials](/tutorials/first-steps/), which iteratively build up the various concepts and features that you'll need to get the most out of your workflows.  

If you want to take a deeper dive into the concepts that make up the Prefect ecosystem, check out our [Concepts documentation](/concepts/overview).

## Quick Start

To jump right in and get started using Prefect 2, you'll need to complete the following steps:

- [Install Prefect](/getting-started/installation/).

That's it! You're ready to [start writing local flows](/tutorials/first-steps/). These flows will appear in the Prefect 2 UI without additional configuration.

If you want to start running flows on a schedule, via the API, from the UI, or on distributed infrastructure, you'll need to understand additional concepts and perform some configuration.

- Start a [Prefect Orion API server](/ui/overview/) with `prefect orion start`.
- Configure [storage](/concepts/storage/) to persist flow and task data.
- Create a [work queue](/concepts/work-queues/#work-queue-overview) to collect scheduled runs for deployments.
- [Start an agent](/concepts/work-queues/#agent-overview) in an environment that can execute work from a work queue.

If you have used Prefect 1 and are familiar with Prefect workflows, we still recommend reading through the [Prefect 2 tutorials](/tutorials/first-steps/). Prefect 2 flows and subflows offer new functionality, and running deployments with [agents and work queues](/tutorials/deployments/) reflects a significant change in how you configure orchestration components.

!!! note "Additional Resources"
    If you don't find what you're looking for here there are many other ways to engage, ask questions and provide feedback:

    - [Prefect's Slack Community](https://www.prefect.io/slack/) is helpful, friendly, and fast growing - come say hi!
    - [Prefect Discourse](https://discourse.prefect.io/) is a knowledge base with plenty of tutorials, code examples, answers to frequently asked questions, and troubleshooting tips. Ask any question or just [browse through tags](https://discourse.prefect.io/docs).
    - [Open an issue on GitHub](https://github.com/PrefectHQ/prefect/issues) for bug reports, feature requests, or general discussion
    - [Email us](mailto:hello@prefect.io) to setup a demo, get dedicated support or learn more about our commercial offerings
