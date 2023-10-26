---
description: Choosing among deployment serving and work pool infrastructure options
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
# Choose how to serve and deploy your flows

In this guide, we will help you choose among Prefect deployment serving options, and if needed, work pool infrastructure types.

We assume that you want to be able to schedule flow runs, so you that means you need a deployment.

Follow the flow chart below and click on the terminal nodes to go to the relevant documentation.

```mermaid
%%{
  init: {
    'theme': 'base',
    'themeVariables': {
      'fontSize': '20px'
    }
  }
}%%

flowchart TD
    A{Need customized <br> or dynamically provisioned <br> infrastructure?}:::green--No-->B[Use flow.serve, <br> likely in a VM]
    A--Yes-->C{Want to run in <br> serverless infrastructure?}:::blue
    C--No-->D{Want to run on Kubernetes?}:::blue
    C--Yes-->E{Able to store <br> credentials on Prefect Cloud?}:::blue
    D--No-->F[Use process work pool, <br> likely in a VM]
    D--Yes-->G[Use Kubernetes <br> work pool]
    E--No-->H[Use serverless <br> non-push work pool]
    E--Yes-->I[Use serverless <br> push work pool]
  

    click B "/tutorial/deployments/" _blank
    click F "/" _blank
    click G "/guides/deployment/kubernetes/" _blank
    click H "https://prefecthq.github.io/prefect-aws/#using-prefect-with-aws-ecs/" _blank
    click I "/guides/deployment/push-work-pools/" _blank

    classDef gold fill:goldenrod,stroke:goldenrod,stroke-width:4px
    classDef yellow fill:gold,stroke:gold,stroke-width:4px:black
    classDef gray fill:lightgray,stroke:lightgray,stroke-width:4px
    classDef blue fill:blue,stroke:blue,stroke-width:4px,color:white
    classDef green fill:green,stroke:green,stroke-width:4px,color:white
    classDef red fill:red,stroke:red,stroke-width:4px,color:white
    classDef orange fill:orange,stroke:orange,stroke-width:4px:black
    classDef dkgray fill:darkgray,stroke:darkgray,stroke-width:4px,color:white
```

## Notes

The first question in the flow chart - "Need customized or dynamically provisioned infrastructure?" - gets at whether you want to run your flows in containers.
Nearly all of the of the options on the "Yes" path use Docker containers so that you can more easily scale your infrastructure up and down.

If you don't need customized or scalable infrastructure, you shouldn't need a worker and work pool and `flow.serve` should meet your needs.

"Want to run in serverless architecture"? gets at whether you want to run your workflows on serverless cloud options on AWS, Azure, or Google Cloud.

If you want to use serverless infrastructure and you're able to store your credentials in a [block(/concepts/blocks/) in our encrypted Prefect Cloud database, then AWS ECS, Azure Container Instances, or Google Cloud Run serverless push work pools are great options.
No worker is required with a push work pool.
Jobs are automatically submitted to your serverless infrastructure.

If push work pools aren't an option for you, you can choose among AWS ECS, Azure Container Instances, Google Cloud Run, or Google Vertex AI serverless work pools.

If you don't want to use serveless, Kubernetes is a very popular option for running workflows at scale.

If you need infrastructure customization and don't run on Kubernetes or serverless infrastructure, a process worker in a cloud VM or on you own server is a good option.

## Next steps

Read more about [deployment concepts](/concepts/deployments/), [scheduling flows](/concepts/schedules/), or [creating a worker-based deployemnt](/guides/prefect-deploy).
