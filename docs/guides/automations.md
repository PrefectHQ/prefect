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
# Failed run notification example
- Can fail on exceptions thrown
- or send notification for a long flow 

# Event based deployment example 
- Based off of certain failures or long flow run, kick off another flow job 
- New deployment -> Alternate data location to pull data from
# Combining both? 
- Longer script that sends notifications on failures, and kicks off deployments based off events emitted