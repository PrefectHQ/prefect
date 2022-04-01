---
description: Best practices for using Python virtual environments when developing Prefect flows.
tags:
    - Python
    - virtual environments
    - conda
    - virtualenv
    - venv
    - development
    - tutorial
    - deployments
---

# Virtual environments

Virtual environments allow you to separate your Python dependencies for each project. Using virtual environments is a highly recommended practice when developing with Python.

## Creating a virtual environment

We recommend reading the documentation for the virtual environment of your choice. We do not recommend a specific environment management tool, but will use `conda` for this tutorial.

In this example, we create an environment named `prefect-dev` with Python 3.8:

```bash
conda create --name prefect-dev python=3.8   
```

Then, we activate the environment:

```bash
conda activate prefect-dev
```

Now, [install Prefect](/getting-started/installation.md):
```bash
pip install prefect>=2.0a
```

## Running a flow in the virtual environment

Save the following script to the file `example.py`:

```python
from prefect import flow

@flow
def my_flow():
    print("Hello world!")

my_flow()
```

You can run this flow in your environment:

```bash
python example.py
```

If you flow has additional dependencies, you can add them to your environment with `pip install`.

When doing ad hoc flow runs (by calling the flow function directly), the flow will always execute in the current environment.

## Running deployed flows in a virtual environment

If you run your Orion API or agent in the virtual environment, all flow runs using the subprocess flow runner will use the same Python environment by default.

This may be desirable for development or in simple cases where your flow does not have many dependencies.

## Specifying a virtual environment on a deployment

You may want your flows to run in a different Python environment than the agent. The subprocess flow runner supports the following virtual environments:

- [conda](https://docs.conda.io/projects/conda/en/latest/user-guide/tasks/manage-environments.html)
- [virtualenv](https://virtualenv.pypa.io/en/latest/)
- [venv](https://docs.python.org/3/library/venv.html)


For example, you can configure the deployment to run in the `prefect-dev` environment described earlier. Save the following to a `example-deployment.py` file:

```python
import sys
from prefect import flow
from prefect.deployments import DeploymentSpec
from prefect.flow_runners import SubprocessFlowRunner

@flow
def my_flow():
    print(f"Hello! Running with {sys.executable}")


DeploymentSpec(
    name="example",
    flow=my_flow,
    flow_runner=SubprocessFlowRunner(condaenv="prefect-dev", stream_output=True)
)
```

Create the deployment:

```bash
prefect deployment create ./example-deployment.py
```

In a separate terminal, start an agent:

```bash
prefect agent start
```

Then create a flow run for the deployment:

```bash
prefect deployment run my-flow/example
```

You should see output from the agent as the flow run is submitted and run in your conda environment.

## Specifying environment paths

Conda environments may also be provided as a path to the prefix:

```python
SubprocessFlowRunner(condaenv="/opt/homebrew/Caskroom/miniconda/base/envs/prefect-dev")
```

Virtualenv and venv environments must be specified as a path:

```python
SubprocessFlowRunner(virtualenv="./my-venv")
```

Relative paths will be resolved relative to the agent's working directory.

Note, the same field is used for both venv and virtualenv.
