---
sidebarDepth: 2
editLink: false
---
# Triggers
---
Triggers are functions that determine if a task should run based on
the state of upstream tasks.

For example, suppose we want to construct a flow with one root task; if this task
succeeds, we want to run task B.  If instead it fails, we want to run task C.  We
can accomplish this pattern through the use of triggers:

```python
import random

from prefect.triggers import all_successful, all_failed
from prefect import task, Flow


@task(name="Task A")
def task_a():
    if random.random() > 0.5:
        raise ValueError("Non-deterministic error has occured.")

@task(name="Task B", trigger=all_successful)
def task_b():
    # do something interesting
    pass

@task(name="Task C", trigger=all_failed)
def task_c():
    # do something interesting
    pass


with Flow("Trigger example") as flow:
    success = task_b(upstream_tasks=[task_a])
    fail = task_c(upstream_tasks=[task_a])

## note that as written, this flow will fail regardless of the path taken
## because *at least one* terminal task will fail;
## to fix this, we want to set Task B as the "reference task" for the Flow
## so that its state uniquely determines the overall Flow state
flow.set_reference_tasks([success])

flow.run()
```

## Functions
|top-level functions: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-triggers-all-finished'><p class="prefect-class">prefect.triggers.all_finished</p>(upstream_states)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/triggers.py#L75">[source]</a></span></div>
<p class="methods">This task will run no matter what the upstream states are, as long as they are finished.<br><br>**Args**:     <ul class="args"><li class="args">`upstream_states (dict[Edge, State])`: the set of all upstream states</li></ul></p>|
 | <div class='method-sig' id='prefect-triggers-manual-only'><p class="prefect-class">prefect.triggers.manual_only</p>(upstream_states)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/triggers.py#L90">[source]</a></span></div>
<p class="methods">This task will never run automatically, because this trigger will always place the task in a Paused state. The only exception is if the "resume" keyword is found in the Prefect context, which happens automatically when a task starts in a Resume state.<br><br>**Args**:     <ul class="args"><li class="args">`upstream_states (dict[Edge, State])`: the set of all upstream states</li></ul></p>|
 | <div class='method-sig' id='prefect-triggers-all-successful'><p class="prefect-class">prefect.triggers.all_successful</p>(upstream_states)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/triggers.py#L106">[source]</a></span></div>
<p class="methods">Runs if all upstream tasks were successful. Note that `SKIPPED` tasks are considered successes and `TRIGGER_FAILED` tasks are considered failures.<br><br>**Args**:     <ul class="args"><li class="args">`upstream_states (dict[Edge, State])`: the set of all upstream states</li></ul></p>|
 | <div class='method-sig' id='prefect-triggers-all-failed'><p class="prefect-class">prefect.triggers.all_failed</p>(upstream_states)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/triggers.py#L122">[source]</a></span></div>
<p class="methods">Runs if all upstream tasks failed. Note that `SKIPPED` tasks are considered successes and `TRIGGER_FAILED` tasks are considered failures.<br><br>**Args**:     <ul class="args"><li class="args">`upstream_states (dict[Edge, State])`: the set of all upstream states</li></ul></p>|
 | <div class='method-sig' id='prefect-triggers-any-successful'><p class="prefect-class">prefect.triggers.any_successful</p>(upstream_states)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/triggers.py#L138">[source]</a></span></div>
<p class="methods">Runs if any tasks were successful. Note that `SKIPPED` tasks are considered successes and `TRIGGER_FAILED` tasks are considered failures.<br><br>**Args**:     <ul class="args"><li class="args">`upstream_states (dict[Edge, State])`: the set of all upstream states</li></ul></p>|
 | <div class='method-sig' id='prefect-triggers-any-failed'><p class="prefect-class">prefect.triggers.any_failed</p>(upstream_states)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/triggers.py#L156">[source]</a></span></div>
<p class="methods">Runs if any tasks failed. Note that `SKIPPED` tasks are considered successes and `TRIGGER_FAILED` tasks are considered failures.<br><br>**Args**:     <ul class="args"><li class="args">`upstream_states (dict[Edge, State])`: the set of all upstream states</li></ul></p>|
 | <div class='method-sig' id='prefect-triggers-not-all-skipped'><p class="prefect-class">prefect.triggers.not_all_skipped</p>(upstream_states)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/triggers.py#L290">[source]</a></span></div>
<p class="methods">Runs if all upstream tasks were successful and were not all skipped.<br><br>**Args**:     <ul class="args"><li class="args">`upstream_states (dict[Edge, State])`: the set of all upstream states</li></ul></p>|
 | <div class='method-sig' id='prefect-triggers-some-failed'><p class="prefect-class">prefect.triggers.some_failed</p>(at_least=None, at_most=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/triggers.py#L174">[source]</a></span></div>
<p class="methods">Runs if some amount of upstream tasks failed. This amount can be specified as an upper bound (`at_most`) or a lower bound (`at_least`), and can be provided as an absolute number or a percentage of upstream tasks.<br><br>Note that `SKIPPED` tasks are considered successes and `TRIGGER_FAILED` tasks are considered failures.<br><br>**Args**:     <ul class="args"><li class="args">`at_least (Union[int, float], optional)`: the minimum number of         upstream failures that must occur for this task to run.  If the         provided number is less than 0, it will be interpreted as a         percentage, otherwise as an absolute number.     </li><li class="args">`at_most (Union[int, float], optional)`: the maximum number of upstream        failures to allow for this task to run.  If the provided number is        less than 0, it will be interpreted as a percentage, otherwise as an        absolute number.  </li></ul></p>|
 | <div class='method-sig' id='prefect-triggers-some-successful'><p class="prefect-class">prefect.triggers.some_successful</p>(at_least=None, at_most=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/triggers.py#L231">[source]</a></span></div>
<p class="methods">Runs if some amount of upstream tasks succeed. This amount can be specified as an upper bound (`at_most`) or a lower bound (`at_least`), and can be provided as an absolute number or a percentage of upstream tasks.<br><br>Note that `SKIPPED` tasks are considered successes and `TRIGGER_FAILED` tasks are considered failures.<br><br>**Args**:     <ul class="args"><li class="args">`at_least (Union[int, float], optional)`: the minimum number of         upstream successes that must occur for this task to run.  If the         provided number is less than 0, it will be interpreted as a         percentage, otherwise as an absolute number.     </li><li class="args">`at_most (Union[int, float], optional)`: the maximum number of upstream         successes to allow for this task to run.  If the provided number is         less than 0, it will be interpreted as a percentage, otherwise as         an absolute number.</li></ul></p>|

<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on August 6, 2020 at 13:56 UTC</p>