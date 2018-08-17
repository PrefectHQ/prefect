
# Triggers and Reference Tasks

In some cases, we explicitly _don't_ want to automate some portion of a system; in these cases the notion of a "Success" can be difficult or impossible to verify automatically, so instead we want a person to review the state of affairs and decide if it's safe to proceed with the work.  Othertimes user input is needed at _task_ runtime (as opposed to _flow_ runtime).

For example, imagine we have the following workflow:

<center><img src="/manual_approval.svg" height=400></center>

### Triggers
In Prefect, this workflow can be implemented through the use of `triggers`.  A `trigger` is a function which determines whether a task should run, fail, or be placed in some other state based on the state of its upstream dependencies.  The default task trigger is (naturally) `all_successful`.  To implement the workflow above, we will use two triggers:
- the `manual_only` trigger, which will cause the task which requires approval to be placed in a `Pending` state until explicitly requested as a `start_task` in a future call to `Flow.run()`
- the `any_failed` trigger so that the complaint is only run if approval _fails_

### Reference Tasks
Notice that in the example above, the terminal task is the complaint task.  Consequently, whenever this task _succeeds_ the overall flow will be considered a success (the default method for determining the overall state of the flow is by considering the states of its terminal tasks).  However, we have found ourselves in a situation where success of the terminal tasks actually implies flow _failure_ - the main objective was not achieved!  This is where `reference_tasks` come into play: `reference_tasks` can be set by the flow and are a list of tasks that will determine the overall state of the flow.  In this case, we have one reference task: the email.  Let's now proceed to set up the flow and walk through the constructs we have discussed.

:::warning NOTE
There are other legitimate implementations of this flow, for example by using `conditionals`.
:::

```python
from prefect import task, Flow
from prefect.triggers import manual_only, any_failed
from prefect.tasks.control_flow import ifelse


@task
def pull_critical_data():
    "Pulls and cleans data, which is then returned."
    return 1


@task
def build_report(data):
    "Compiles data into a report which is saved somewhere."
    return 'quality report'


@task(trigger=manual_only)
def email_report_to_board(report):
    """
    Emails `report` as an attachment to entire board of directors.
    
    Returns `True` if email is sent correctly, `False` otherwise.
    """
    return True


@task(trigger=any_failed)
def complain_to_data_analyst():
    "Alerts the appropriate person to review reporting code."
    pass


with Flow() as f:
    data = pull_critical_data()
    report = build_report(data)
    board_email = email_report_to_board(report)
    complaint = complain_to_data_analyst(upstream_tasks=[board_email])
```

:::tip 
We were able to _functionally_ specify upstream dependencies on the `complaint` task via the reserved `upstream_tasks` keyword argument.
:::

Next, we need to set `board_email` as our only reference task so that the overall state of the flow is representative of our target objective.


```python
f.set_reference_tasks([board_email])
```

We are now ready to run the flow:


```python
flow_state = f.run(return_tasks=[report, board_email, complaint])

print("Flow state: {}\n".format(flow_state))
print(flow_state.result)

##    Flow state: Pending("Some terminal tasks are still pending.")
    
##    Flow results: {
##     <Task: build_report>: Success("Task run succeeded."), 
##     <Task: email_report_to_board>: Pending("Trigger function is "manual_only""), 
##     <Task: complain_to_data_analyst>: Pending()
##     }
```

Let's have a look at what the current flow state looks like visually:

<img src='/manual_only.png'>


We can now inspect the `report` to decide if we would like to proceed:


```python
flow_state.result[report].result
### 'quality report'
```


Looks good to me!  Since we aren't running this tutorial with a Prefect server, we now need to explicitly tell the flow to run beginning at the `board_email` task.

:::tip 
Anytime a task is included in `start_tasks`, its trigger is ignored and it attempts to run.  
:::

Note that in this case, the tasks represented by `data` and `report` will _not_ be run again - the necessary inputs required for `board_email` to run have been cached!


```python
new_flow_state = f.run(task_states=flow_state.result, 
                       start_tasks=[board_email], 
                       return_tasks=[board_email, complaint])

print("Flow state: {}\n".format(new_flow_state))
print(new_flow_state.result)

##    Flow state: Success("All reference tasks succeeded.")
    
##    Flow result: { 
##       <Task: email_report_to_board>: Success("Task run succeeded."), 
##       <Task: complain_to_data_analyst>: TriggerFailed("Trigger was "any_failed" but none of the upstream tasks failed.")
##       }
```
<img src='/successful_reference_tasks.png'>
