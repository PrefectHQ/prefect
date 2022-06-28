---
sidebarDepth: 1
---

# Slack Notifications

![slack-banner](https://uploads-ssl.webflow.com/5ba446b0e783e26d5a2f2382/5bc4f20bd534b99be66f24aa_slack.png){.viz-md}

!!! warning Deprecation warning

    Note that this tutorial is outdated and will be removed in a future release.

    For Slack notifications, we recommend:

    - [Automations](/orchestration/ui/automations.html)
    - [SlackTask](/api/latest/tasks/notifications.html#slacktask)
    - [Notifications and State Handlers](/core/concepts/notifications.html)

    You'll find an excellent tutorial demonstrating [How to send Slack notifications using the SlackTask](https://discourse.prefect.io/t/how-to-send-slack-notifications-using-the-slacktask/497) in the [Prefect Community Discourse](https://discourse.prefect.io/).



Prefect lets you easily setup callback hooks to get notified when certain state changes occur within your flows or for a given task.
This can be as simple as:

```python
from prefect import Flow, task
from prefect.utilities.notifications import slack_notifier


@task(name="1/x task", state_handlers=[slack_notifier])
def div(x):
    return 1 / x


@task(name="Add 1 task", state_handlers=[slack_notifier])
def add(x):
    return x + 1


with Flow('Add Divide Flow') as f:
    res = div(x=add(-1))


final_state = f.run()
```

Which will produce the following messages in your channel of choice:

![slack channel flow notifications](/example_slack.png){.viz-xl .viz-padded}

This can be further customized to only report on certain state changes, or you can use this tool as a building block for more complicated notification logic!
In the near future, you'll be able to directly access the UI from links provided in the notifications, and even manually resume your workflows, all from within Slack!
Before you can begin experimenting though, you need to install the Prefect Slack app to your workspace of choice.

## Installation Instructions

Currently, the Prefect slack app can only be installed with a "secret" installation URL. Eventually it will be installable by searching for it in the Slack App Directory, but not today. Given this, please be mindful of sharing this URL: [installation URL](https://prefect-slack.appspot.com).

After navigating to the installation URL, you can select the workspace and specific channel you want Prefect to post to (creating a designated #prefect channel could come in handy here). For example, if I want notifications to come directly to me in a private message:

![prefect slack integration](/slack_page1.png){.viz-lg}

After making your decisions, click the green "Authorize" button to proceed. Assuming all goes well, you should be greeted with a successful landing page that looks something like:

![slack hook authorized](/slack_page2.png){.viz-xl .viz-padded}

That's it! Save the URL in your secure location of choice.

!!! tip Multiple Installations
    It's perfectly OK to integrate the Prefect App multiple times into the same workspace; for example, you and a coworker who both use Prefect might want customized notifications. Follow these steps as many times as you desire, but make sure to keep track of which channel each URL is attached to!

## Using your URL to get notifications

You can store your slack webhook URL in your secure database of Prefect Secrets under `"SLACK_WEBHOOK_URL"`. 

Alternatively, for testing and development, you can include it in the `[context.secrets]` section of your prefect configuration file. To do so, create a file `~/.prefect/config.toml` and place the following into it:

```
[context.secrets]
SLACK_WEBHOOK_URL = "https://hooks.slack.com/services/XXXXXXXXX/xxxxxxxxx/XXXXXXXXXXX"
```

!!! warning Storing Secrets
    This method of storing secrets is intended _only_ for local development and testing! For production usage, use a Prefect Secret instead.

Almost there - all that's left is to actually hook up the `slack_notifier` state handler to your favorite task or flow! All task and flow initializations accept an optional `state_handler` keyword argument. This should consist of a _list_ of "state handler" callables with call signature

```python
def generic_state_handler(task_or_flow, old_state, new_state):
    # ...
    # implement your favorite custom logic to occur on state changes
    # ...
    return new_state # this is important
```

This function will be called every time your task (or flow) undergoes a state change. In the example at hand, `slack_notifier` is already setup as a state handler for you!
Consequently, as we saw in the introduction example, you can provide `slack_notifier` as a `state_handler` for any task / flow you want.

## Customizing your alerts

The default settings are to be notified on _every_ state change for the task / flow the `slack_notifier` is registered with. There are three easy ways of customizing your Prefect slack alerts:

- ignore certain state changes with the `ignore_states` keyword argument
- alert only on certain state changes with the `only_states` keyword argument
- implement your own state handler which calls out to `slack_notifier`

The `slack_notifier` state handler is [_curried_](https://en.wikipedia.org/wiki/Currying), meaning you can call it early to bind certain keyword arguments. For example, suppose we only wanted to be notified on `Failed` states; in that case, we could do:

```python
from prefect import task
from prefect.engine.state import Failed
from prefect.utilities.notifications import slack_notifier

handler = slack_notifier(only_states=[Failed]) # we can call it early

@task(state_handlers=[handler])
def add(x, y):
    return x + y
```

Happy slacking!
