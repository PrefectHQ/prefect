## Improvements

**Agents to Workers**

- Improved visibility into the status of the worker such as when workers were started and when they last polled.
- Improved accommodation of high availability use cases.

**Infra Blocks to Work Pools**

- New push work pools (beta) allow for flow execution without the need for a worker at all!
- As an advanced feature, the interface between the prefect worker and flow run infrastrucure is exposed through the `job_configuration`. This enables an unprecedented level of customization and governance.

**New prefect.yaml file for managing multiple deployments**

- Its easier than before to define many deployments en mass through a prefect.yaml file.
- Prefect provides actions that allow you to automatically build images for your flows.
- Templating enables dryer deployment definitions.
- You get a wizard now! 🧙

----------

#### If you are more familiar with the agent pattern let me provide a few translations:

1. **Command to build deployments:** 
    
    `prefect deployment build <entrypoint>` --> `prefect deploy` 
    
    Prefect will now automatically detect flows in your repo and provide a wizard 🧙 to guide you through setting required attributes for your deployments.

2. **Configuring remote flow code storage:** storage blocs --> pull action
    
    Though you can still use an existing storage block as your pull action!

3. **Configuring flow run infrastructure:** run-infrastructure blocks --> typed work pool 
    
    Infra config is now set on the typed Work Pool.

4. **Managing multiple deployments:**
    
    Create and/or update many deployments en mass through a `prefect.yaml` file.


### **What stays the same**:

- Storage blocks can be set as the pull action.
- Infra config fields from infra blocks have parity with typed work-pool fields
- Deployment-level infra-overrides operate in much the same way. `infra_override` -> `job_variable`
- The process for starting an agent and starting a worker in your environment are virtually identical.
    
    `prefect agent start <work pool>` --> `prefect worker start <work pool>`
