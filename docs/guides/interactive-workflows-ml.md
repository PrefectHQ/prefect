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

## Using Human Input with Large Language Model Deployment

Large language models (LLMs) have gained popularity in various natural language processing (NLP) tasks. However, they often lack the ability to handle nuanced or ambiguous queries effectively. To address this, human input can be incorporated into LLM deployment workflows. This allows for improved performance and accuracy in NLP tasks by providing easy opportunities for human reviewers.

### Surfacing different deployment architectures for LLM applications

- Serverless deployments: using AWS Lambda to provide auto-scaling pay per use LLM hosting
- Cloud-native deployment: containers, kubernetes, and service mesh architecture
- Hybrid on-premise and cloud infrastructures: using pre-existing enterprise networks mixed with emerging cloud technologies
- Using hosted services: interacting with external endpoints' managed execution

By integrating human input, LLMs can be used in human-in-the-loop workflows, where human reviewers can provide feedback or clarification on model outputs. This feedback can be used to improve the model's performance and ensure even more accurate results.

For example, for any data quality checks for an upstream workflow, it can be easy to include an approval step in the middle of execution

```python
from prefect import flow, task, get_run_logger, pause_flow_run
from prefect.artifacts import create_table_artifact
from prefect.input import RunInput
from enum import Enum
from typing import Optional
import requests

class Title(Enum):
    Mr = "Mr"
    Mrs = "Mrs"
    Ms = "Ms"
    Dr = "Dr"

class Approval(Enum):
    Approve = "Approve"
    Reject = "Reject"

class NameInput(RunInput):
    title: Optional[Title]
    first_name: Optional[str]  
    last_name: Optional[str]  
    description: Optional[str]
    approve: Approval = Approval.Reject  

@task(name="Fetching URL", retries = 1, retry_delay_seconds = 5, retry_jitter_factor = 0.1)
def fetch(url: str):
    logger = get_run_logger()
    response = requests.get(url)
    raw_data = response.json()
    logger.info(f"Raw response: {raw_data}")
    return raw_data

@task(name="Cleaning Data")
def clean(raw_data: dict):
    results = raw_data.get('results')[0]
    logger = get_run_logger()
    logger.info(f"Cleaned results: {results}")
    return results['name']

@flow(name="Create Names")
def create_names(num: int = 2):
    df = []
    url = "https://randomuser.me/api/"
    logger = get_run_logger()
    copy = num
    while num != 0:
        raw_data = fetch(url)
        df.append(clean(raw_data))
        num -= 1
    logger.info(f"create {copy} names: {df}")
    return df

@flow(name="Redeploy Flow")
def redeploy_flow():
    logger = get_run_logger()
    user_input = pause_flow_run(wait_for_input = NameInput)
    if user_input.first_name != None:
        logger.info(f"User input: {user_input.first_name} {user_input.last_name}!")
    # raw type of user_input
    input = {'title': user_input.title.value, 
             'first': user_input.first_name, 
             'last': user_input.last_name}
    list_of_names.append(input)
    if(user_input.approve.value == 'Approve'):
        logger.info(f"Report approved! Creating artifact...")
        create_table_artifact(
            key="name-table",
            table=list_of_names,
            description = user_input.description
        )
    else:
        raise Exception("User did not approve")

if __name__ == "__main__":
    list_of_names = create_names()
    redeploy_flow()  
```

Let us start with a simple training example, where we are pulling data from some external location, and choosing the engine we want to use in our analysis. 

We will be using Marvin, an open source integration that makes working with LLM's easy to use, to help visualize this interaction more. 

## Find a way with interactive workflows 
Interactive workflows enable seamless collaboration between LLMs and human reviewers. Prefect allows for pausing, suspending, and resuming the execution of a flow, while providing opportunities for human reviewers to intervene and provide input when necessary.

Prefect offers guardrails in being able to set these executions in a native python way while providing different interfaces to update your work.

