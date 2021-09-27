# Getting Started

## Welcome

Welcome to the Prefect Orion project.

Check out our [introductory tutorial](tutorials/introductory.md) first!

Or, read about:

- [The main concepts in Prefect](concepts/overview.md)
- The Prefect community
- [Frequently asked questions](faq.md)

## Quickstart 

Want a quick look at how it works? Follow along below.

### Installation

```bash
pip install prefect-orion
```

See the [full installation instructions](getting-started/installation.md) for more details on installation.

### Writing your first flow

```python
from prefect import flow

@flow
def hello(name: str = "world"):
    """
    Say hello to `name`
    """
    print(f"Hello {name}!")

# Run the flow with default parameters
hello()
```

Save the code to `hello_flow.py` then run it with `python hello_flow.py`. You should see it print "Hello world!"

### Writing a flow with tasks

Flows can contain tasks. Tasks expose features like concurrency, caching, retries, etc. Here, we'll just use them to isolate some steps of our workflow.

```python
from prefect import flow, task
from random import randint

NAMES = ["earth", "sun", "moon"]

@task
def pick_name():
    # Select a random name from our constant
    return NAMES[randint(0, len(NAMES))]

@task
def say_hello(name: str):
    print(f"Hello {name}!")

@flow
def hello(name: str = None):
    """
    Say hello to `name` if given; otherwise pick a random name!
    """
    if not name:
        name = pick_name()

    say_hello(name)

# Run the flow with default parameters
hello()
```

Save the code to `hello_flow_tasks.py` then run it with `python hello_flow_tasks.py`. You should see it say hello to a random name!



