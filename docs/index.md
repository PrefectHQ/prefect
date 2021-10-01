---
hide:
  - navigation
  - toc
---
<figure markdown=1>
![](./img/prefect-orion-logo-dark.svg){width=500px}
</figure>

#
**Don't Panic.** Prefect Orion is the second-generation workflow orchestration engine from [Prefect](https://www.prefect.io), now available as a technical preview. 

Orion was designed from the ground up to handle the dynamic, scalable workloads that the modern data stack demands. Powered by a brand-new, async rules engine, it represents years of research, development, and dedication to a simple idea: **you should love your workflows again**.

Read the docs, run the code, or host the UI. Join thousands of community members in [Slack](https://www.prefect.io/slack) to share your thoughts and feedback.

!!! info "Please note"
    Orion is under active development and will change rapidly. For production use, please prefer [Prefect Core](https://github.com/prefecthq/prefect).

---


```python
from prefect import flow

@flow
def hello(name: str = "world"):
    """
    Say hello to `name`
    """
    print(f"Hello, {name}!")

hello() # Hello, world!
hello(name="Marvin") # Hello, Marvin!

# Now spin up a UI to see these flow runs!
```

---

## [Getting Started](getting-started/overview/)
[Install](getting-started/installation.md) Prefect, then dive into the [tutorial](tutorials/first-steps/).

## [Concepts](concepts/overview.md)

Learn more about Orion's design by reading our [concept docs](concepts/overview.md).

## [Frequently Asked Questions](faq.md)

Orion represents a fundamentally new way of building and orchestrating data workflows. Learn more about our plans by reading the [FAQ](faq.md).
