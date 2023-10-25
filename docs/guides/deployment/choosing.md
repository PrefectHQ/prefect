---
description: Choosing among deployment creation, deployment serving and work pool options.
tags:
    - orchestration
    - deploy
    - deployments
    - serve
    - prefect.yaml
    - infrastructure
    - work pool
    - worker
search:
  boost: 2
---
# Choosing how to build and serve a deployment

In this guide, we will help you choose among Prefect deployment creation, deployment serving, and work pool options.

We assume that you want to be able to schedule flow runs, so you that means you need a deployment.

Click on the terminal nodes in the diagram below to go to the relevant documentation.

```mermaid
%%{
  init: {
    'theme': 'base',
    'themeVariables': {
      'fontSize': '19px'
    }
  }
}%%

flowchart TD
    A{Need customized <br> or dynamically provisioned <br> infrastructure?}:::green--No-->B[Use flow.serve, likely in a cloud VM]
    A--Yes-->C{Want to run in <br> serverless infrastructure?}:::yellow
    C--No-->D[Want to run on managed K8s?]:::orange
    C--Yes-->E{Able to store <br> credentials on Prefect Cloud}:::blue
    D--No-->B
    D--Yes-->G[Use a K8s work pool]
    E--No-->H[Use serverless non-push work pool]
    E--Yes-->I[Use serverless push work pool]
  

    click B "/tutorial/deployments/" _blank
    click G "/guides/deployment/kubernetes/" _blank
    click H "https://prefecthq.github.io/prefect-aws/#using-prefect-with-aws-ecs/" _blank
    click I "/guides/deployment/push-work-pools/" _blank

    classDef gold fill:goldenrod,stroke:goldenrod,stroke-width:4px
    classDef yellow fill:gold,stroke:gold,stroke-width:4px
    classDef gray fill:lightgray,stroke:lightgray,stroke-width:4px
    classDef blue fill:blue,stroke:blue,stroke-width:4px,color:white
    classDef green fill:green,stroke:green,stroke-width:4px,color:white
    classDef red fill:red,stroke:red,stroke-width:4px,color:white
    classDef orange fill:orange,stroke:orange,stroke-width:4px
    classDef dkgray fill:darkgray,stroke:darkgray,stroke-width:4px,color:white
```
