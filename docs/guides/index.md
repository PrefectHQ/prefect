---
description: Learn how to do common workflows with Prefect.
title: Guides
tags:
    - guides
    - how to
search:
  boost: 2
---

# Guides

This section of the documentation contains guides for common workflows and use cases.

## Development

| Title                                                  | Description                                                                                        |
| -------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| [Hosting](/guides/host/) | Host your own Prefect server instance. |
| [Profiles & Settings](/guides/settings/) | Configure Prefect and save your settings. |
| [Logging](/guides/logs/) | Configure Prefect's logger and aggregate logs from other tools. |
| [Runtime Context](/guides/runtime-context/) | Enable a flow to access metadata about itself and its context when it runs.  |
| [Variables](/guides/variables/) | Store and retrieve configuration data. |
| [Using the Client](/guides/using-the-client/) | Make API calls with the Python client |

## Execution

| Title                                                  | Description                                                                                        |
| -------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| [Docker](/guides/docker/) | Deploy flows with Docker containers. |
| [Webhooks](/guides/webhooks/) | Receive, observe, and react to events from other systems. |
| [State Change Hooks](/guides/state-change-hooks/) | Execute code in response to state changes. |
| [Dask and Ray](/guides/dask-ray-task-runners/) | Scale your flows with parallel computing frameworks. |
| [Moving Data](/guides/moving-data/) | Move data to and from cloud providers.  |
| [Global Concurrency Limits](/guides/global-concurrency-limits/) | Limit concurrent flow runs. |

## Workers and agents

| Title                                                  | Description                                                                                        |
| -------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| [Deploying Flows to Work Pools and Workers](/guides/prefect-deploy/) | Learn how to easily manage your code and deployments. |
| [Upgrade from Agents to Workers](/guides/upgrade-guide-agents-to-workers/) | Why and how to upgrade from Agents to Workers. |
| [Kubernetes](/guides/deployment/kubernetes/) | Deploy flows on Kubernetes. |
| [Serverless Push Work Pools](/guides/deployment/push-work-pools/) |  Run flows on serverless infrastructure without a worker. |
| [Serverless Work Pools with Workers](/guides/deployment/serverless-workers) |  Run flows on serverless infrastructure with a worker. |
| [Storage](/guides/deployment/storage-guide/) | Store your code for deployed flows. |

## Other guides

| Title                                                  | Description                                                                                        |
| -------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| [Testing](/guides/testing/) | Easily test your workflows. |
| [Troubleshooting](/guides/troubleshooting/) | Identify and resolve common issues with Prefect. |
| [Custom Workers](/guides/deployment/developing-a-new-worker-type/) | Develop your own worker type. |
| [Prefect Recipes](../recipes/recipes/) |  Common, extensible examples for setting up Prefect. |

!!! tip "Need help?"
    Get your questions answered by a Prefect Product Advocate! [Book a Meeting](https://calendly.com/prefect-experts/prefect-product-advocates?utm_campaign=prefect_docs_cloud&utm_content=prefect_docs&utm_medium=docs&utm_source=docs)
