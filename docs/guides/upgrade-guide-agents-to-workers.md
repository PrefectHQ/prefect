# How to Upgrade from Agents to Workers

## Enhancements

**Agents to Workers**

- Improved visibility into the status of the worker such as when workers were started and when they last polled.
- Better handling of race conditions for high availability use cases.

**Infra Blocks to Work Pools**

- Work pools expose `job_configuration` that enable an unprecedented level of customization and governance.
- New push work pools (beta) allow for flow execution without the need to host a worker.

**New `prefect.yaml` file for managing multiple deployments**

- Its easier than before to define many deployments en mass through a prefect.yaml file.
- Prefect provides actions that allow you to automatically build images for your flows.
- Templating enables dryer deployment definitions.
- You get a [wizard now](/#step-5-deploy-the-flow)! 🧙

----------

## What's changing

1. **Command to build deployments:** 
    
    `prefect deployment build <entrypoint>` --> `prefect deploy` 
    
    Prefect will now automatically detect flows in your repo and provide a wizard 🧙 to guide you through setting required attributes for your deployments.

2. **Configuring remote flow code storage:** 
    
    storage blocs --> pull action
    
    Though you can still use an existing storage block as your pull action!

3. **Configuring flow run infrastructure:** 
    
    run-infrastructure blocks --> typed work pool 
    
    Infra config is now set on the typed Work Pool.

4. **Managing multiple deployments:**
    
    Create and/or update many deployments en mass through a `prefect.yaml` file.


## What stays the same

- Storage blocks can be set as the pull action in a `prefect.yaml` file.
- Infra blocks have similar configuration fields as typed work pools.
- Deployment-level infra-overrides operate in much the same way. 

    `infra_override` -> `job_variable`

- The process for starting an agent and starting a worker in your environment are virtually identical.
    
    `prefect agent start <work pool>` --> `prefect worker start <work pool>`


## How to get started quickly

If you have a deployment with a storage block and infra block, here's how to quickly upgrade it to use Prefect's new features:

1. Create a work pool of type that matches whichever run-infrastructure block you are currently using. 

    1. Any work pool infrastructure type aside from `Prefect Agent` should work.
    2. Referencing the configurations you've set on the infrastructure block, set similar flow run infrastructure configurations on the work pool.

2. Start a worker to poll this work pool. You should see the command to start the worker as soon as you save your new work pool. 

    !!! Tip "Process for starting a worker is very similar to the process for starting a worker."
        Notice the command to start a worker is very similar to the command to start an agent. If you previously used terraform, a helm chart, or other infra as code method to start your agent, you should be able to continue using it for the worker provided the word `agent` is changed to `worker`.

3. Deploy your flow:
    ```bash
    prefect deploy
    ```
4. In your prefect.yaml file, configure a pull step referencing whatever configuration you used as your storage block.

