---
description: Prefect deployments encapsulate a flow, allowing flow runs to be scheduled and triggered via API.
tags:
    - orchestration
    - flow runs
    - deployments
    - schedules
    - triggers
    - prefect.yaml
    - infrastructure
    - storage
    - work pool
    - worker
search:
  boost: 2
---

# Deployments

A deployment is a server-side concept that encapsulates a flow, allowing it to be scheduled and triggered via API. The deployment stores metadata about where your flow's code is stored and how your flow should be run.

Each deployment references a single "entrypoint" flow (though that flow may, in turn, call any number of tasks and subflows). Any single flow, however, may be referenced by any number of deployments.

At a high level, you can think of a deployment as configuration for managing flows, whether you run them via the CLI, the UI, or the API.

## Deployments overview

All Prefect flow runs are tracked by the API. The API does not require prior registration of flows. With Prefect, you can call a flow locally or on a remote environment and it will be tracked.

Creating a _deployment_ for a Prefect workflow means packaging workflow code, settings, and infrastructure configuration so that the workflow can be managed via the Prefect API and run remotely by a Prefect agent.

The following diagram provides a high-level overview of the conceptual elements involved in defining a deployment and executing a flow run based on that deployment.

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
    D --> E("<div style='margin: 5px 10px 5px 5px;'>Agent</div>"):::red
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

!!! info "Your flow code and the Prefect hybrid model"
    In the diagram above, the dotted line indicates the path of your flow code in the lifecycle of a Prefect deployment, from creation to executing a flow run. Notice that your flow code stays within your storage and execution infrastructure and never lives on the Prefect server or database.

    This is the heart of the Prefect hybrid model: there's always a boundary between your code, your private infrastructure, and the Prefect backend, such as [Prefect Cloud](/ui/cloud/). Even if you're using a self-hosted Prefect server, you only register the deployment metadata on the backend allowing for a clean separation of concerns.

When creating a deployment, a user must answer *two* basic questions:

- What instructions does a [worker](/concepts/work-pools/) need to set up an execution environment for my workflow? For example, a workflow may have Python requirements, unique Kubernetes settings, or Docker networking configuration.
- How should the flow code be accessed?

A deployment additionally enables you to:

- Schedule flow runs.
- Specify event triggers for flow runs.
- Assign a work queue name to delegate deployment flow runs to work queues.
- Assign one or more tags to organize your deployments and flow runs. You can use those tags as filters in the Prefect UI.
- Assign custom parameter values for flow runs based on the deployment.
- Create ad-hoc flow runs from the API or Prefect UI.
- Upload flow files to a defined storage location for retrieval at run time.
- Specify run time infrastructure for flow runs, such as Docker or Kubernetes configuration.