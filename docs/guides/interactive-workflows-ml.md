---
description: Exploring the functionality for ML usecases with interactive workflows.
tags:
        - flow run
        - pause
        - suspend
        - input
        - human-in-the-loop workflows
        - interactive workflows
        - Machine learning
        - Large language models
search:
    boost: 2
---

## Using Human Input with Large Language Model Deployment

Large language models (LLMs) have gained popularity in various natural language processing (NLP) tasks. However, they often lack the ability to handle nuanced or ambiguous queries effectively. To address this, human input can be incorporated into LLM deployment workflows. This allows for improved performance and accuracy in NLP tasks by providing easy opportunities for human reviewers.

### Surfacing different deployment architectures for LLM applications

- Serverless deployments: using AWS Lambda to provide auto-scaling pay per use LLM hosting
- Cloud-native deployment: containers, kubernetes, and service mesh architecture
- Hybrid on-premise and cloud infrastructures: using pre-existing enterprise networks mixed with emerging cloud technologies
- Using hosted services: interacting with external endpoints' managed execution

By integrating human input, LLMs can be used in human-in-the-loop workflows, where human reviewers can provide feedback or clarification on model outputs. This feedback can be used to improve the model's performance and ensure even more accurate results.

Let us start with a simple training example, where we are pulling data from some external location, and choosing the engine we want to use in our analysis. 

We will be using Marvin, an open source integration that makes working with LLM's easy to use, to help visualize this interaction more. 

## Find a way with interactive workflows 
Interactive workflows enable seamless collaboration between LLMs and human reviewers. Prefect allows for pausing, suspending, and resuming the execution of a flow, while providing opportunities for human reviewers to intervene and provide input when necessary.

Prefect offers guardrails in being able to set these executions in a native python way while providing different interfaces to update your work.