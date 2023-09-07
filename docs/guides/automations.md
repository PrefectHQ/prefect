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

# Failed run notification example
- Can fail on exceptions thrown
- or send notification for a long flow 

# Event based deployment example 
- Based off of certain failures or long flow run, kick off another flow job 
- New deployment -> Alternate data location to pull data from
# Combining both? 
- Longer script that sends notifications on failures, and kicks off deployments based off events emitted