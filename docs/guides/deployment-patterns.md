---
description: Answers to frequently asked questions about Prefect.
tags:
    - FAQ
    - frequently asked questions
    - questions
    - license
    - databases
---





### Patterns in Prefect
There are four common dataflow design patterns in Prefect. Each pattern offers different degrees and types of separation from related flows.

 - Conceptual separation is when a flow can be thought of as separate from another flow, even if it’s part of the same process.

 - Execution separation is when a flow can be executed separately from another flow.

 - Awareness separation is when a flow doesn’t have any direct reference to another flow, even if it’s related.



### Monoflow
![Monoflow diagram](/img/guides/monoflow.png)

A monoflow is a single flow made up of series of tasks with data passed from one to the next. Within the flow, tasks are tightly coupled to each other through dependencies. It is the most common way to use Prefect. It’s the pattern that most people think of when they think of workflow orchestrators.

This pattern is most useful for most common, straightforward flows. There’s only two levels of abstraction to think about—the flow itself and the tasks within it. It’s an easy pattern to set up, maintain, and use, especially if the flow is fully owned and maintained by a single person or team. However, this pattern can get unwieldy when there are multiple code owners, many tasks, or tasks with different infrastructure needs within the same flow.

Here is an example of how a monoflow would look like:
```python
import httpx
from prefect import flow, get_run_logger

@flow
def get_repo_info(repo_name: str = "PrefectHQ/prefect"):
    url = f"https://api.github.com/repos/{repo_name}"
    response = httpx.get(url)
    response.raise_for_status()
    repo = response.json()
    logger = get_run_logger()
    logger.info(f"PrefectHQ/prefect repository statistics 🤓:")
    logger.info(f"Stars 🌠 : {repo['stargazers_count']}")
    logger.info(f"Forks 🍴 : {repo['forks_count']}")

if __name__ == "__main__":
    get_repo_info()
```

### Flow of subflows
![flow of deployments diagram](img/guides/subflow.png)

Prefect’s orchestration engine is the first to offer first-class subflows. Any flow written with Prefect can be used as a component in another flow. A subflow has the same relationship to its parent flow as a task does. It runs in the same process as its parent flow. You can use subflows much as you would use an imported module in a python script.

This pattern is most useful when you only want conceptual separation. It increases conceptual overhead in the form of additional layers of abstraction: the parent flow, its task and subflow runs, and the subflow runs’ tasks. In exchange, this pattern compartmentalizes the components of the parent process. For an individual, this can be useful for decomposing large flows into more easily reasoned logical units. For teams, it facilitates clear ownership boundaries and facilitates code-reuse.

Lets try to configure the monoflow example to be a flow of subflows. 
```python
import httpx
from prefect import flow

@flow(log_prints = True)
def get_repo_info():
    url = 'https://api.github.com/repos/PrefectHQ/prefect'
    api_response = httpx.get(url)
    if api_response.status_code == 200:
        repo_info = api_response.json()
        stars = repo_info['stargazers_count']
        forks = repo_info['forks_count']
        contributors_url = repo_info['contributors_url']
        average_commits = calculate_average_commits(contributors_url)
        print(f"PrefectHQ/prefect repository statistics 🤓:")
        print(f"Stars 🌠 : {stars}")
        print(f"Forks 🍴 : {forks}")
        print(f"Average commits per contributor 💌 : {average_commits:.2f}")
    else:
        raise Exception('Failed to fetch repository information.')
    
@flow()
def calculate_average_commits(contributors_url):
    response = httpx.get(contributors_url)
    if response.status_code == 200:
        contributors = len(response.json())
    else:
        raise Exception('Failed to fetch contributors.')      
    commits_url = f'https://api.github.com/repos/PrefectHQ/prefect/stats/contributors'
    response = httpx.get(commits_url)
    if response.status_code == 200:
        commit_data = response.json()
        total_commits = sum(c['total'] for c in commit_data)
        average_commits = total_commits / contributors
        return average_commits
    else:
        raise Exception('Failed to fetch commit information.')

if __name__ == "__main__":
    calculate_average_commits()
```

### Flow of deployments
![Deployments diagram](img/guides/deployment.png)

Prefect flows can also start a run of another flow through a deployment—a specification that associates a flow with a particular infrastructure. In this case, the deployed flow isn’t so much “part of” the initial flow, as it is “called by” that flow. Once a flow has called another flow, it can wait for it to complete, or it can simply start the deployed flow and proceed with the rest of its tasks. A deployed flow can run on separate infrastructure from the initial flow. Our community calls this the orchestrator pattern. Prefect users can think of and use deployed flows much like an external web service.

This pattern is most useful when you want both conceptual and execution separation. The conceptual complexity is about the same as using a subflow, but the execution complexity is greater, because there’s separate infrastructure and processes to think about. Still, the complexity can be worth it, particularly when certain tasks need a certain type of infrastructure, like GPUs.

TODO: Test flow name

```python
from my_project.flows import calculate_average_commits
from prefect.deployments import Deployment

@flow
def build_deployments(name):
    deployment = Deployment.build_from_flow(
    flow=name,
    name=f"{name}-deployment", 
    version=1, 
    work_queue_name="default",
    work_pool_name="default-agent-pool",
)
    deployment.apply()

if __name__ == "__main__":
    build_deployments(calculate_average_commits)
```

### Event Triggered Flow

![Event diagram](img/guides/event.png)

With Prefect’s automations release, a new pattern is now possible. Whenever a flow run changes state, as it does when it starts or completes running, it emits an event signaling the change to the rest of the system. With automations, Prefect can trigger flows based on a specific flow run state change, or lack thereof. Just as with a submitted flow, a triggered flow can run on separate infrastructure from the initial flow.

This pattern is most useful when you want conceptual, execution, and awareness separation. In this pattern, the triggered flow doesn’t need to know anything about the initial flow. The event that triggers it could come from anywhere. It could even be one of several events that the trigger is listening for. We expect that users will adopt this pattern for the similar reasons that any organization might adopt an event-driven architecture. The loose coupling enables more distributed software and minimizes coordination costs.

For example, you could send an event in your workflow where an Automation can kick off another deployment based off its response. 

```python
def some_function(name: str="Marvin") -> None:
    print(f"hi {name}!")
    emit_event(event=f"{name}.sent.event!", resource={"prefect.resource.id": f"test-event-{name}"})

```
You are able to emit an event within a function to have more lightweight interaction with Prefect. The only necessary fields are the event name and the resource.id which you are able to trigger different actions. Create custom triggers from events like down below:
```json
{
  "match": {
    "prefect.resource.id": "test-event-Marvin"
  },
  "match_related": {},
  "after": [],
  "expect": [
    "Marvin.sent.event!"
  ],
  "for_each": [],
  "posture": "Reactive",
  "threshold": 1,
  "within": 0
}
``` 

With events you are able to explore different responses, and have a fine tune control over the full functionality of [Automations](https://docs.prefect.io/2.10.21/cloud/automations/).

Keep in mind, this event driven workflow allows you to supercharge interactions between multiple workspaces by exploring event webhooks. Find more information on how to do so in the [event webhooks](https://docs.prefect.io/2.10.21/cloud/webhooks/#webhook-templates) documentation. 

### Use the right pattern for the job with Prefect
The way flows are designed and composed has implications for how they perform, how they’re maintained, and how they’re used. Legacy data pipeline frameworks lock you into a one-size-fits-all pattern, appropriate for some circumstances, but not all. Prefect is designed for incremental change. You and your team can transition between patterns as requirements demand, perhaps starting with a monoflow, and decomposing it over time. With this flexibility, you can choose the patterns that best suit your data, your challenge, and your organization. Checkout all of the github examples at this repository here, and feel free to contribute more examples!