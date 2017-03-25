"""
Triggers are functions that determine whether a task should run.

Triggers are passed the task in question and a list of states from any tasks
that come immediately before the task. They return True if the tasks should run
and False otherwise.
"""

from prefect.state import State

def all_success(task, before_task_states):
    return all([s == State.SUCCESS for s in before_task_states])

def all_failed(task, before_task_states):
    return all([s == State.FAILED for s in before_task_states])

def any_success(task, before_task_states):
    return any([s == State.SUCCESS for s in before_task_states])

def any_failed(task, before_task_states):
    return any([s == State.FAILED for s in before_task_states])

def one_success(task, before_task_states):
    return len([s == State.SUCCESS for s in before_task_states]) == 1

def one_failed(task, before_task_states):
    return len([s == State.FAILED for s in before_task_states]) == 1
