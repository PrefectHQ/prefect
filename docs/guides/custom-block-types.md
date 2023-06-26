## Why Blocks

Today there are many low-code data integration tools - “connectors” to popular applications. These tools are great for setting up connections to common systems, but they’re not code-first, or even code-second. It can be complex to do anything custom with these tools.

**Low-code connectors often come in two kinds - sources and destinations.** That’s great for straightforward ELT pipelines, but modern dataflows don’t just extract and load data. They write intermediate outputs, call out to web services, transform data, train models, set up job-specific infrastructure, and much more.

Prefect’s [Blocks](/concepts/blocks/) offer the advantages of low-code connectors with a first class experience in code. The code first approach means Blocks are connectors for code that can go beyond source and destination.

## Why Create Custom Block Types

Prefect offers a wide variety of block types straight out of the box. However, it doesn't limit you there. You can easily create custom block types to meet the specific needs of your project by inheriting from the base block class. After all, at their core, blocks are nothing more than your friendly neighborhood Python class.

With custom block types, as your data platform evolves, your building blocks don’t have to be replaced. Instead, they can gain new capabilities.



### 1. Inherit from Block Class

```python
from prefect.blocks.core import Block

class MyCustomBlock(Block):

    """
    This is what my block does!
    """
```

!!! Tip "Inline documentation is key!" 
    Doc strings will be added directly to the UI.