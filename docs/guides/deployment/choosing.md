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

In this guide, we will help you choose among Prefect deployment creation, deployment serving, and work pool options

We assume that you want to be able to schedule flow runs, so you that means you need a deployment.

##

```mermaid
%%{
  init: {
    'theme': 'base',
    'themeVariables': {
      'fontSize': '19px'
    }
  }
}%%

flowchart LR
    F("<div style='margin: 5px 10px 5px 5px;'>Flow Code</div>"):::yellow -.-> A("<div style='margin: 5px 10px 5px 5px;'>Deployment Definition</div>"):::gold
    subgraph Server ["<div style='width: 150px; text-align: center; margin-top: 5px;'>Prefect API</div>"]
        D("<div style='margin: 5px 10px 5px 5px;'>Deployment</div>"):::green
    end
    subgraph Remote Storage ["<div style='width: 160px; text-align: center; margin-top: 5px;'>Remote Storage</div>"]
        B("<div style='margin: 5px 6px 5px 5px;'>Flow</div>"):::yellow
    end
    subgraph Infrastructure ["<div style='width: 150px; text-align: center; margin-top: 5px;'>Infrastructure</div>"]
        G("<div style='margin: 5px 10px 5px 5px;'>Flow Run</div>"):::blue
    end

    A --> D
    D --> E("<div style='margin: 5px 10px 5px 5px;'>Worker</div>"):::red
    B -.-> E
    A -.-> B
    E -.-> G

    classDef gold fill:goldenrod,stroke:goldenrod,stroke-width:4px
    classDef yellow fill:gold,stroke:gold,stroke-width:4px
    classDef gray fill:lightgray,stroke:lightgray,stroke-width:4px
    classDef blue fill:blue,stroke:blue,stroke-width:4px,color:white
    classDef green fill:green,stroke:green,stroke-width:4px,color:white
    classDef red fill:red,stroke:red,stroke-width:4px,color:white
    classDef dkgray fill:darkgray,stroke:darkgray,stroke-width:4px,color:white
```

Questions

1. Do you need customized or dynamically provisioned infrastructure?
    No:
        Use flow.serve likely in a cloud VM - see forthcoming guide (could run in Docker container on the VM)
    Yes
        1. Want to run in Severless?
            No
            1. Want to run on managed K8s?
                No
                    1. Want to run in
                Yes
                    Grab a helm chart and see the nice K8s guide
            Yes
                1. Want/able to use a push work pool (no worker required)
                    Yes
                        Use a push work pool - see the guide
                    No
                        Use a serveless (non-push work pool) - also gives option for Vertex AI - Jeff working on combo guide
