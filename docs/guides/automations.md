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

# Preparing Automations

From the Automations tutorial, we were able to see the capabilities of what an automation can do and how to configure them within the UI. 

In this guide, we will showcase common usecases where automations can shine when responding to your workflows. We will create a simple notificaiton automation first. Then build upon that with an event based automation. Lastly, we will combine these ideas to create a well alerted and responsive deployment pattern. 

TODO: create a warning saying it is only available for Prefect Cloud

# Cleaning data Example
TODO: Find dataset to use or can pull from an api
Automations are great when handling mixed outcome workflows, as you are able to respond to specific actions done by the orchestrator. 
For example, let us try to grab data from an API and if we run into any issues, lets try react to the workflow end results. 

We can get started by pulling data from this endpoint in order to do some data cleaning and transformations. 

Let us create a simple extract method, that pulls the data from the endpoint. 

```python
from prefect import flow, task, get_run_logger
import requests
import json
import pandas as pd

@task
def fetch(url: str):
    response = requests.get(url)
    raw_data = response.json()
    return raw_data

@task
def clean(raw_data: dict):
    results = raw_data.get('results')[0]
    return results['name']

@flow
def build_names():
    df = []
    count = 10
    url = "https://randomuser.me/api/"
    while count != 0:
        raw_data = fetch(url)
        df.append(clean(raw_data))
        count-=1
    print(df)
    return df

if __name__ == "__main__":
    build_names()
```
TODO: concurrently write to a list with the new names

From here, we can see that the data cleaning workflow has visibility into each step, and we are sending a list of names to our next step of our MLOPS pipeline.

TODO: make the dataframe more complex -> with more features?

# Failed run notification example
- Can fail on exceptions thrown
- or send notification for a long flow 

Now let us try to send a notification based off a failed state outcome. We can configure a notification to be thrown so that we know when to look into our workflow logic. 

Prior to creating the automation, let us confirm the notification location. We have to create a notification block to help define where the notification will be thrown. 

Let us navigate to the blocks page on the UI, and lets click into creating an email notification block. 

Now that we have created the notification block, we can move towards the automations page. 

Easily we can create an automation in the UI that allows us to click through the set up steps. First we start off by navigating to the automations page within the UI. 

Next we try to find the trigger type, in this case let us do a flow failure (keep in mind task failures get cascading upstream back to the parent flow). 

Finally, let us create the actions that will be done once the triggered is hit. In this case, let us create a notification to be sent out to showcase the failure. 

# Event based deployment example 
- Based off of certain failures or long flow run, kick off another flow job 
- Showcase creating an automation via the rest api based on a trigger from an event
- Automation kicks off another deployment
- New deployment -> Alternate data location to pull data from

```python
def create_event_driven_auto():
    api_url = "https://api.prefect.cloud/api/accounts/{account_id}/workspaces/{workspace_id}/automations/"
    todo = {
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
    response = requests.post(api_url, json=todo)
    
    print(response.json())
    return response.json()
```
# Combining both? 
- Longer script that sends notifications on failures, and kicks off deployments based off events emitted (probably not needed)