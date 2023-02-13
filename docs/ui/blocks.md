---
description: Create and manage blocks from the Prefect UI and Prefect Cloud.
tags:
    - UI
    - blocks
    - storage
    - Prefect Cloud
    - secrets
---

# Blocks

Blocks enable you to store configuration and provide an interface for interacting with external systems. With blocks, you are able to securely store credentials for authenticating with services like AWS, GitHub, Slack, or any other system you'd like to orchestrate with Prefect. 

Blocks are the underlying components behind familiar Prefect concepts like [deployments](/concepts/deployments/) and [storage](/concepts/storage/). To learn more about creating and using blocks programmatically, see the [Blocks](/concepts/blocks/) documentation.

You can create, edit, and manage blocks in the Prefect UI and Prefect Cloud. On a Prefect server, blocks are created in the server's database. On Prefect Cloud, blocks are created on a workspace.

Select the **Blocks** page to see all blocks currently defined on your Prefect server instance or Prefect Cloud workspace.

![Viewing configured blocks in the Prefect UI](../img/ui/blocks.png)

You can get the identifier for any storage block, edit the block, or delete the block by selecting the button to the right of the block.

To create a new block, select the **+** button. Prefect displays a library of block types you can configure to create blocks to be used by your flows.

![Viewing the new block library in the Prefect UI](../img/ui/block-library.png)

Select the block type, then provide the information needed to make the block functional. For example, here we're configuring a Slack Webhook block.

![Configuring a Slack Webhook block in the Prefect UI](../img/ui/blocks-slack.png)

The [Blocks](/concepts/blocks/) documentation provides further detail on using blocks in your Prefect flows.