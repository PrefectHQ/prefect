# Getting Started

Welcome to Prefect!  

Whether you've been working with Prefect for years or this is your first time, this collection of tutorials will guide you through the process of defining, running, monitoring and eventually automating your first Prefect Orion workflow.  

First and foremost, you'll need [a working version of Prefect Orion installed](installation.md).  

From there, you can [follow along with the tutorials](/tutorials/first-steps/), which iteratively build up the various concepts and features that you'll need to get the most out of your workflows.  

If you want to take a deeper dive into the concepts that make up the Prefect ecosystem, check out our [Concepts documentation](/concepts/overview).

## Quick Start

To jump right in and get started using Prefect Orion, you'll need to complete the following steps:

- [Install Prefect](/getting-started/installation/).

That's it! You're ready to [start writing local flows](/tutorials/first-steps/) and use the Prefect Orion UI to monitor those flows.

If you want to start scheduling flows or using deployments to trigger flow runs via the API or UI, you'll need to set up a few additional Prefect features. 

2. Start a [Prefect Orion API server](/ui/overview/) with `prefect orion start`.
3. Configure [storage](/concepts/storage/) to persist flow and task data.
4. Create a [work queue](/concepts/work-queues/#work-queue-overview) to collect scheduled runs for deployments.
5. [Start an agent](/concepts/work-queues/#agent-overview) in an environment that can execute work from a work queue.

If you have used Prefect Core and are familiar with Prefect workflows, we still recommend reading through the [Orion tutorials](/tutorials/first-steps/). Orion flows and subflows offer new functionality, and running deployments with [work queues and agents](/tutorials/deployments/) reflects a significant change in how you configure orchestration components.

!!! note "Additional Resources"
    If you don't find what you're looking for here there are many other ways to engage, ask questions and provide feedback:

    - [Prefect's Slack Community](https://www.prefect.io/slack/) is helpful, friendly, and fast growing - come say hi!
    - [Prefect Discourse](https://discourse.prefect.io/) is a knowledge base with plenty of tutorials, code examples, answers to frequently asked questions, and troubleshooting tips. Ask any question or just [browse through tags](https://discourse.prefect.io/docs).
    - [Open an issue on GitHub](https://github.com/PrefectHQ/prefect/issues) for bug reports, feature requests, or general discussion
    - [Email us](mailto:hello@prefect.io) to setup a demo, get dedicated support or learn more about our commercial offerings
