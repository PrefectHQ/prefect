---
description: Exploring the functionality for ML usecases with interactive workflows.
tags:
        - flow run
        - pause
        - suspend
        - input
        - human-in-the-loop workflows
        - interactive workflows
        - Machine learning
        - Large language models
search:
    boost: 2
---

## Using Human Input within MLOps

This approach involves incorporating human judgment into AI systems to improve their accuracy, reliability, and performance. In the context of generative AI, which focuses on creating new, diverse, and innovative outputs, HITL can play a pivotal role in refining the models and ensuring that the generated content meets the desired standards and aligns with ethical guidelines.


Generative AI applications have gained popularity recently and have spurred a movement in unlocking various usecases within data science and engineering. Human in the loop workflows have provided ways to include human interaction within many steps of a machine learning and data pipeline. This guide is meant to address different applications that Prefect can support, and provide ease of use when creating such systems. This allows for improved performance and accuracy in various data ingestion and machine learning tasks by providing easy opportunities for human reviewers.

### Data ingestion human interaction

Often times the amount of data needed for any analysis or model can change from time to time, even with the input source staying consistnent. For example, for any data quality checks for an upstream workflow, it can be easy to include an approval step in the middle of its execution. In this example below, we can specify how many users we would like to pull information on. 

```python
from prefect.input import RunInput
from prefect import get_run_logger
from prefect.blocks.system import JSON
from prefect import task, flow, get_run_logger, pause_flow_run
import requests

URL = "https://randomuser.me/api/"


class UserInput(RunInput):
    number_of_users: int


@task(name="Fetching URL", retries=1, retry_delay_seconds=5, retry_jitter_factor=0.1)
def fetch(url: str):
    logger = get_run_logger()
    response = requests.get(url)
    raw_data = response.json()
    logger.info(f"Raw response: {raw_data}")
    return raw_data


@flow(name="Create Names")
def create_names():
    logger = get_run_logger()
    df = []
    description_md = """
    How many users would you like to create?
    """
    user_input = pause_flow_run(
        wait_for_input=UserInput.with_initial_data(
            description=description_md, number_of_users=2
        )
    )
    num_of_rows = user_input.number_of_users
    copy = num_of_rows
    while num_of_rows != 0:
        raw_data = fetch(URL)
        df.append(raw_data)
        num_of_rows -= 1
    logger.info(f"create {copy} names: {df}")
    JSON(value=df).save("all-users-json", overwrite=True)
    return df


if __name__ == "__main__":
    list_of_names = create_names()
```
We can see how easy it is to suspend the process, include human input, and resume it in within the Prefect Cloud UI. The UI inherits the datatypes from the underlying Pydantic model, so it is easy to provide a polished input box. Let us explore how we can extend this functionality further, by incorporating human input in the cleaning step. 


### Using human input to choose the # of features to drop
We can see how human input can be so beneficial during the data collection portion of any analysis. Additionally, any data refinement steps such as choosing the # of features to drop can be beneficical in cleaning the dataset even further. Similarly, we can pause the execution and resume once we know which features we would want pulled. 

Let us add a clean function, and another place to provide a user input for the # of features to drop from the data pulled. 

```python

```

Let us explore how we can act upon this new artifact downstream.

### Using human input to create Prefect objects
Let us extend this idea further, by pulling the JSON data and asking for input to create a Prefect artifact.

## Find a way with interactive workflows 
Interactive workflows enable seamless collaboration between workflows and human reviewers. Prefect allows for pausing, suspending, and resuming the execution of a flow, while providing opportunities for human reviewers to intervene and provide input when necessary.

Prefect offers guardrails in being able to set these executions in a native python way while providing different interfaces to update your work.

