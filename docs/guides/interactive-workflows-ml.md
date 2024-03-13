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

```python title="data-ingestion-example.py"
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
We can see how human input can be beneficial during the data collection portion of any analysis. Additionally, any data refinement steps such as choosing the # of features to drop can be beneficical in cleaning the dataset even further. Similarly, we can pause the execution and resume once we know which features we would want pulled. 

Let us add a clean function, and another area to provide a user input for the # of features to drop from the data pulled. 

```python title="data-ingestion-example.py" hl_lines="50-67 88 84"
from prefect.input import RunInput
from prefect import get_run_logger
from prefect.blocks.system import JSON
from prefect import task, flow, get_run_logger, pause_flow_run
import requests

URL = "https://randomuser.me/api/"

DEFAULT_FEATURES_TO_DROP = [
    "email",
    "login",
    "dob",
    "registered",
    "phone",
    "cell",
    "id",
    "nat",
]


class CleanedInput(RunInput):
    features_to_drop: list[str]


class UserInput(RunInput):
    number_of_users: int


@task(name="Fetching URL", retries=1, retry_delay_seconds=5, retry_jitter_factor=0.1)
def fetch(url: str):
    logger = get_run_logger()
    response = requests.get(url)
    raw_data = response.json()
    logger.info(f"Raw response: {raw_data}")
    return raw_data


@task(name="Cleaning Data")
def clean(raw_data: dict, features_to_drop: list[str]):
    results = raw_data.get("results")[0]
    logger = get_run_logger()
    keysList = list(results.keys())
    logger.info(f"Columns available: {keysList}")
    z = list(set(keysList) - set(features_to_drop))
    logger.info(f"Features to drop: {features_to_drop}")
    return list(map(results.get, z))


# HIL: user input for which features to drop initially
@flow(name="User Input Remove Features")
def user_input_remove_features(url: str):
    raw_data = fetch(url)

    features = "\n".join(raw_data.get("results")[0].keys())

    description_md = (
        "## Features available:"
        f"\n```json{features}\n```\n"
        "Which columns would you like to drop?"
    )

    user_input = pause_flow_run(
        wait_for_input=CleanedInput.with_initial_data(
            description=description_md, features_to_drop=DEFAULT_FEATURES_TO_DROP
        )
    )
    return user_input.features_to_drop


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
    features_to_drop = user_input_remove_features(URL)
    logger.info(f"Features to drop: {features_to_drop}")
    while num_of_rows != 0:
        raw_data = fetch(URL)
        df.append(clean(raw_data, features_to_drop))
        num_of_rows -= 1
    logger.info(f"created {copy} users: {df}")
    JSON(value=df).save("all-users-json", overwrite=True)
    return df


if __name__ == "__main__":
    list_of_names = create_names()
```

We can incrementally improve our data ingestion flow to take in another input during the cleaning step of the dataset. Often times cleaning a dataset and understanding its inputs to further clean it can be tedious, but interactive workflows enable users to streamline this action within the same process.

### Using human input to create Prefect objects
Let us extend this idea further, by pulling the cleaned JSON data and asking for input to create a Prefect artifact. Data quality checks can be very cumbersome, and require a user to juggle many different platforms to ensure the data has come in as expected. We can surface the newly created JSON block to the user, and provide input if we would want to create a Prefect artifact based off of it. Let us extend this example and provide another flow to help create this artifact.


**`data-ingestion-example.py`**
```python
from prefect.input import RunInput
from prefect import get_run_logger
from prefect.blocks.system import JSON
from prefect import task, flow, get_run_logger, pause_flow_run
from pydantic import Field
from prefect.artifacts import create_table_artifact
import requests

URL = "https://randomuser.me/api/"

DEFAULT_FEATURES_TO_DROP = [
    "email",
    "login",
    "dob",
    "registered",
    "phone",
    "cell",
    "id",
    "nat",
]

class CreateArtifact(RunInput):
    create_artifact: bool = Field(description="Would you like to create an artifact?")


class CleanedInput(RunInput):
    features_to_drop: list[str]


class UserInput(RunInput):
    number_of_users: int


@task(name="Fetching URL", retries=1, retry_delay_seconds=5, retry_jitter_factor=0.1)
def fetch(url: str):
    logger = get_run_logger()
    response = requests.get(url)
    raw_data = response.json()
    logger.info(f"Raw response: {raw_data}")
    return raw_data


@task(name="Cleaning Data")
def clean(raw_data: dict, features_to_drop: list[str]):
    results = raw_data.get("results")[0]
    logger = get_run_logger()
    keysList = list(results.keys())
    logger.info(f"Columns available: {keysList}")
    z = list(set(keysList) - set(features_to_drop))
    logger.info(f"Features to drop: {features_to_drop}")
    return list(map(results.get, z))


# HIL: user input for which features to drop initially
@flow(name="User Input Remove Features")
def user_input_remove_features(url: str):
    raw_data = fetch(url)

    features = "\n".join(raw_data.get("results")[0].keys())

    description_md = (
        "## Features available:"
        f"\n```json{features}\n```\n"
        "Which columns would you like to drop?"
    )

    user_input = pause_flow_run(
        wait_for_input=CleanedInput.with_initial_data(
            description=description_md, features_to_drop=DEFAULT_FEATURES_TO_DROP
        )
    )
    return user_input.features_to_drop


@flow(name="Create Artifact")
def create_artifact():
    description_md = f"""
    Information pulled: {JSON.load("all-users-json")}
    Would you like to create an artifact?
    """
    logger = get_run_logger()
    create_artifact = pause_flow_run(
        wait_for_input=CreateArtifact.with_initial_data(
            description=description_md, create_artifact=False
        )
    )
    print(type(JSON.load("all-users-json")))
    if create_artifact.create_artifact == True:
        logger.info("Report approved! Creating artifact...")
        create_table_artifact(key="name-table", table=JSON.load("all-users-json").value)
    else:
        raise Exception("User did not approve")


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
    features_to_drop = user_input_remove_features(URL)
    logger.info(f"Features to drop: {features_to_drop}")
    while num_of_rows != 0:
        raw_data = fetch(URL)
        df.append(clean(raw_data, features_to_drop))
        num_of_rows -= 1
    logger.info(f"created {copy} users: {df}")
    JSON(value=df).save("all-users-json", overwrite=True)
    return df


if __name__ == "__main__":
    list_of_names = create_names()
    create_artifact()
```

Artifacts are a great centralized way to house markdown, tables, and other data types in a collaborative way. This object offers a revision history, type information, parent flow name, and other relevant meta data to understand the timeline of this artifact. 

## Data Enrichment with Marvin
Even after pulling data from various sources, cleaning it based on biases needed for any machine learning job, we can often enrich the dataset with new features based on EDA or other factors. We can use Marvin to help simplify any data enrichment and updates to our dataset, without the need for further cleaning steps. Please refer to the Marvin (documentation on getting set up)[https://www.askmarvin.ai/welcome/tutorial/]. 

We can use the extract function from Marvin to help pull necessary information from our dataset, and we can extend the functionality of how we can use it by providing other user inputs if needed. 

```python title="marvin_extension.py.py"
import marvin
from prefect.blocks.system import Secret
from prefect import flow, task, get_run_logger, pause_flow_run
from prefect.input import RunInput
from prefect.blocks.system import JSON

DEFAULT_EXTRACT_QUERY = (
    "Group by location and count the number of users in each location."
)


class InputQuery(RunInput):
    input_instructions: str


@flow(name="Extract User Insights")
def extract_information():
    secret_block = Secret.load("openai-creds-interactive-workflows")
    marvin.settings.openai.api_key = secret_block.get()

    description_md = f"""
    The most recent user information: {JSON.load("all-users-json")}
    What would you like to gain insights on?
    """
    logger = get_run_logger()
    user_input = pause_flow_run(
        wait_for_input=InputQuery.with_initial_data(
            description=description_md,
            input_instructions=DEFAULT_EXTRACT_QUERY,  # Create a table of a users name, location, coordinates, and continent the user is located
        )
    )

    logger = get_run_logger()

    logger.info(
        f"""
    Extracting user insights... \n
    User input: {user_input.input_instructions}
    """
    )
    result = marvin.extract(
        JSON.load("all-users-json"),
        target=str,
        instructions=user_input.input_instructions,
    )
    logger.info(f"Query results: {result}")
    return result
```

We can refer to this flow in our original example, and use this interaction to enrich our current dataset.

```python title="data-ingestion-example.py" hl_lines="6"
import marvin_extension as ai_functions
...
if __name__ == "__main__":
    list_of_names = create_names()
    create_artifact()
    ai_functions.extract_information()
```

## Find a way with interactive workflows 
Interactive workflows enable seamless collaboration between workflows and human reviewers. Prefect allows for pausing, suspending, and resuming the execution of a flow, while providing opportunities for human reviewers to intervene and provide input when necessary.

Prefect offers guardrails in being able to set these executions in a native python way while providing different interfaces to update your work.

