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

Questions

1. Need customized or dynamically provisioned infrastructure?
    No:
        Use `flow.serve``, likely in a cloud VM - see forthcoming guide (could run in Docker container on the VM)
    Yes
        1. Want to run in Serverless?
            No
            1. Want to run on K8s?
                No
                    1.
                Yes
                    Grab a helm chart and see the nice K8s guide
            Yes
                1. Want/able to use a push work pool (no worker required)
                    Yes
                        Use a push work pool - see the guide
                    No
                        Use a serveless (non-push work pool) - also gives option for Vertex AI - Jeff working on combo guide
