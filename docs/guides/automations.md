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

In this guide, we will showcase common usecases where automations can shine when responding to your workflows. We will create a simple notification automation first. Then build upon that with an event based automation. Lastly, we will combine these ideas to create a well alerted and responsive deployment pattern. 

!!! Warning "Available only on Prefect Cloud"
        Automations are only available on Prefect Cloud, please refer to the Cloud documentation to see what 
        additional features are available such as Events and webhooks!


# Creating the test script

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
def build_names(num: int):
    df = []
    url = "https://randomuser.me/api/"
    logger = get_run_logger()
    while num != 0:
        raw_data = fetch(url)
        df.append(clean(raw_data))
        num-=1
    logger.info(f"Built {num} names: {df}")
    return df

if __name__ == "__main__":
    build_names(10)
```

From here, we can see that the data cleaning workflow has visibility into each step, and we are sending a list of names to our next step of our pipeline.

# Completed run notification example

Now let us try to send a notification based off a completed state outcome. We can configure a notification to be thrown so that we know when to look into our workflow logic. 

1. Prior to creating the automation, let us confirm the notification location. We have to create a notification block to help define where the notification will be thrown. 
![List of available blocks](/img/guides/block-list.png)

2. Let us navigate to the blocks page on the UI, and lets click into creating an email notification block. 
![Creating a notification block in the Cloud UI](/img/guides/notification-block.png)

3. Easily we can create an automation in the UI that allows us to click through the set up steps. First we start off by navigating to the automations page within the UI. 
![Automations page](/img/guides/automation-list.png)

4. Next we try to find the trigger type, in this case let us do a flow failure (keep in mind task failures get cascading upstream back to the parent flow). 

![Trigger type](img/guides/automation-triggers.png)

Finally, let us create the actions that will be done once the triggered is hit. In this case, let us create a notification to be sent out to showcase the completion. 

!!! Warning "No deployment created"
        Keep in mind, we did not need to create a deployment to trigger our automation, where a state outcome of a local flow run helped trigger this notification block.  


# Event based deployment example 
- Showcase creating an automation via the rest api based on a trigger from an event
- Automation kicks off another deployment
- New deployment -> Alternate data location to pull data from
We can create an automation that can help kick off a deployment instead of a notification. Let us explore how we can programatically create this automation. We will take advantage of our extensive REST API catelog to help 'automate' the creation of this Automation.  

Additionally, find more information in our [REST API documentation](https://docs.prefect.io/latest/api-ref/rest-api/#interacting-with-the-rest-api) on how to interact with the endpoints further. 

Let us first create an automation via a POST call against our API. Ensure you have your api_key, account_id, and workspace_id are handy. 


```python
def create_event_driven_automation():
    api_url = f"https://api.prefect.cloud/api/accounts/{account_id}/workspaces/{workspace_id}/automations/"
    data = {
    "name": "Event Driven Redeploy",
    "description": "Programatically created an automation to redeploy a flow based on an event",
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
        "string"
    ],
    "for_each": [
        "string"
    ],
    "posture": "Reactive",
    "threshold": 0,
    "within": 0
    },
    "actions": [
    {
        "type": "do-nothing"
    }
    ],
    "owner_resource": "string"
        }
    
    headers = {"Authorization": f"Bearer {PREFECT_API_KEY}"}
    response = requests.post(api_url, headers=headers, json=data)
    
    print(response.json())
    return response.json()
```

Let us take a quick peek at the Prefect.yaml file associated with the deployment. We can see that it is very barebones..
# Combining both? 
- Longer script that sends notifications on failures, and kicks off deployments based off events emitted (probably not needed)

TODO: Automations script that trains a model as a next steps? 
- Some sort of MLOPS next steps so the guide seems organic