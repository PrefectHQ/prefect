---
description: Prefect walkthrough on how to use automations and common best practices 
tags:
    - automations
    - event-driven
    - trigger
title: Automations and Common Use Cases
search:
  boost: 2
---

# Using Automations to respond to your workflows

From the Automations tutorial, we were able to see the capabilities of what an automation can do and how to configure them within the UI. 

In this guide, we will showcase common usecases where automations can shine when responding to your workflows. First we will create a simple notification automation. Then build upon that with an event based automation where a deployment will be kicked off. Lastly, we will combine these ideas to create a well alerted and responsive deployment pattern. 

!!! Warning "Available only on Prefect Cloud"
        Automations are only available on Prefect Cloud, please refer to the Cloud documentation to see what 
        additional features are available such as Events and webhooks!


## Creating the test script

Automations are great when handling mixed outcome workflows, as you are able to respond to specific actions done by the orchestrator. 
For example, let us try to grab data from an API and have a notification get kicked off of our end state. 

We can get started by pulling data from this endpoint in order to do some data cleaning and transformations. 

Let us create a simple extract method, that pulls the data from the endpoint. 

```python
from prefect import flow, task, get_run_logger
import requests
import json
import pandas as pd

@task
def fetch(url: str):
    logger = get_run_logger()
    response = requests.get(url)
    raw_data = response.json()
    logger.info(f"Raw response: {raw_data}")
    return raw_data

@task
def clean(raw_data: dict):
    print(raw_data.get('results')[0])
    results = raw_data.get('results')[0]
    logger = get_run_logger()
    logger.info(f"Cleaned results: {results}")
    return results['name']

@flow
def build_names(num: int = 10):
    df = []
    url = "https://randomuser.me/api/"
    logger = get_run_logger()
    copy = num
    while num != 0:
        raw_data = fetch(url)
        df.append(clean(raw_data))
        num-=1
    logger.info(f"Built {copy} names: {df}")
    return df

if __name__ == "__main__":
    list_of_names = build_names()
```

From here, we can see that the data cleaning workflow has visibility into each step, and we are sending a list of names to our next step of our pipeline.

## Create notification block within the UI

Now let us try to send a notification based off a completed state outcome. We can configure a notification to be thrown so that we know when to look into our workflow logic. 

1. Prior to creating the automation, let us confirm the notification location. We have to create a notification block to help define where the notification will be thrown. 
![List of available blocks](/img/guides/block-list.png)

2. Let us navigate to the blocks page on the UI, and click into creating an email notification block. 
![Creating a notification block in the Cloud UI](/img/guides/notification-block.png)

3. Now that we created a notification block, we can go to the automations page to create our first automation.
![Automations page](/img/guides/automation-list.png)

4. Next we try to find the trigger type, in this case let us do a flow completion (keep in mind task failures get cascading upstream back to the parent flow). 

![Trigger type](/img/guides/automation-triggers.png)

Finally, let us create the actions that will be done once the triggered is hit. In this case, let us create a notification to be sent out to showcase the completion. 
![Notification block in automation](/img/guides/notify-auto-block.png)

Now the automation is ready to be triggered from a flow run completion. Let us locally run the file and see that the notification being sent to our inbox after the completion.
![Final notification](/img/guides/final-automation.png)

!!! Tip "No deployment created"
        Keep in mind, we did not need to create a deployment to trigger our automation, where a state outcome of a local flow run helped trigger this notification block. We are not tied to creating a full deployment in order to have safe responses to our desired outcomes.

# Event based deployment automation 
We can create an automation that can help kick off a deployment instead of a notification. Let us explore how we can programatically create this automation. We will take advantage of our extensive REST API catelog to help 'automate' the creation of this automation.  

Additionally, find more information in our [REST API documentation](https://docs.prefect.io/latest/api-ref/rest-api/#interacting-with-the-rest-api) on how to interact with the endpoints further.

Let us have local deployment created where we can kick off some work based on the completion. The automation runs after a long time spent waiting for the notification to get thrown. Let us have this deployment be kicked off from 10 seconds of the flow running.

By following the deployment steps, we can create a local prefect.yaml that looks like this for our flow `build_names`

Let us take a quick peek at the Prefect.yaml file associated with the deployment. We can see that it is very barebones..

!!! Tip "Find deployment_id from the CLI"
      The quickest way to see the ID's associated with your deployment would be running `prefect deployment ls`
      in an authenticated command prompt, and you will be able to see the id's associated with all of your deployments

```bash 
prefect deployment ls
                                          Deployments                                           
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Name                                                  ┃ ID                                   ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ Extract islands/island-schedule                       │ d9d7289c-7a41-436d-8313-80a044e61532 │
│ generate-data-for-patient/example-deployment          │ 107924b8-8ecb-4af3-bd26-fcfaced5ecc4 │
│ generate-data-for-patients/original                   │ 2b779805-abd8-4f54-9f6f-429f1481f33a │
│ generate-data-for-patients/parent                     │ d876a9aa-077c-4abf-8c23-ac9838a8a11e │
│ get-repo-info/test-deployment                         │ fea0c255-eef5-4eba-8970-fdeb47b4f906 │
│ log-flow/my-git-deployment                            │ 002e25d2-7132-4e44-aad8-ba4753f659e8 │
│ ride-duration-prediction/my-first-deployment          │ 5aaf0e2c-3f6d-40d9-a233-144d5f4d2c34 │
│ ride-duration-prediction-backfill/backfill-deployment │ 76dc6581-1773-45c5-a291-7f864d064c57 │
└───────────────────────────────────────────────────────┴──────────────────────────────────────┘
``` 
Let us first create an automation via a POST call against our API. Ensure you have your api_key, account_id, and workspace_id are handy. 

```python
def create_event_driven_automation():
    api_url = f"https://api.prefect.cloud/api/accounts/{account_id}/workspaces/{workspace_id}/automations/"
    data = {
    "name": "Event Driven Redeploy",
    "description": "Programmatically created an automation to redeploy a flow based on an event",
    "enabled": "true",
    "trigger": {
    "match": {
        "property1": "string",
        "property2": "string"
    },
    "match_related": {
        "property1": "string",
        "property2": "string"
    },
    "after": [
        "string"
    ],
    "expect": [
        "prefect.flow-run.Completed"
    ],
    "for_each": [
        "prefect.resource.id"
    ],
    "posture": "Reactive",
    "threshold": 0,
    "within": 0
    },
    "actions": [
    {
        "type": "run-deployment",
        "source": "selected",
        "deployment_id": "", 
        "parameters": "10"
    }
    ],
    "owner_resource": "string"
        }
    
    headers = {"Authorization": f"Bearer {PREFECT_API_KEY}"}
    response = requests.post(api_url, headers=headers, json=data)
    
    print(response.json())
    return response.json()
```


After finding the deployment_id, you can pull the id into the rest api endpoint to help create this automation. 
After running this function, you will see within the UI the changes that came from the post request. Keep in mind, the context will be "custom" on UI. 

Let us run the underlying automation and see the deployment get kicked off after 30 seconds elapsed. This will result in a new flow run of create_names, and we are able to see this new deployment get initiated with the custom parameters we outlined above. 

In a few quick changes, we are able to programatically create an automation that deploys workflows with custom parameters. 

TODO: Question to explore, does flow.serve provide a deployment_id that you could use to then kick off work?
TODO: Deployment that recreates the same 20 names creation except with a different endpoint or feature


# Using an underlying .yaml file

We can extend this idea one step further by utilizing our own .yaml interpretation of the automation, and registering that file with our UI. 

Let us first start with creating the .yaml file that will house the automation requirements. Here is how it would look like:

```yaml
name: Cancel long running flows
description: Cancel any flow run after an hour of execution
trigger:
  match:
    "prefect.resource.id": "prefect.flow-run.*"
  match_related: {}
  after:
    - prefect.flow-run.Failed
  expect:
    - "prefect.flow-run.*"
  for_each:
    - "prefect.resource.id"
  posture: Proactive
  threshold: 1
  within: 3600
actions:
  - type: "cancel-flow-run"
```

TODO: Make it a little bit more robust
Is kicking off a deployment the right thing to do in this case? I like cancelling long running flows -> can tie in with the first example of pulling in lots of data (increase the name count when creating the dataframe)

- Longer script that sends notifications on failures, and kicks off deployments based off events emitted (probably not needed)

# AI function extension

We can take advantage of Marvin that will help classify the data we are pulling in. Additionally, we can use Marvin to help replicate a dataset we could use. Based on the automation trigger, we will call the underlying deployment to kick off the workflow. 

Let us look at this example below using Marvin's AI functions. We will be taking in a dataframe and use the function to create additional features from the data. 

TODO: Automations script that trains a model as a next steps? 
- Some sort of MLOPS next steps so the guide seems organic

Here is an example of pulling in that data and classifying using Marvin AI. We can simplify a classification model in a few functions using the underlying OpenAI model. 


```python
from marvin import ai_classifier
from enum import Enum


@ai_classifier
class CustomerIntent(Enum):
    """Classifies the incoming users intent"""

    SALES = 1
    TECHNICAL_SUPPORT = 2
    BILLING_ACCOUNTS = 3
    PRODUCT_INFORMATION = 4
    RETURNS_REFUNDS = 5
    ORDER_STATUS = 6
    ACCOUNT_CANCELLATION = 7
    OPERATOR_CUSTOMER_SERVICE = 0


CustomerIntent("I got double charged, can you help me out?")
```
