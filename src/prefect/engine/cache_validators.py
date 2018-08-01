"""
Cache validators are functions that determine if a task's output cache
is still valid, or whether that task should be re-run.

A cache validator returns True if the cache is still valid, and False otherwise.
"""
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Dict, Iterable


def never_use(state, inputs, parameters) -> bool:
    return False


def duration_only(state, inputs, parameters) -> bool:
    if state.cache_expiration is None:
        return True
    elif state.cache_expiration > datetime.utcnow():
        return True
    else:
        return False


def all_parameters(state, inputs, parameters) -> bool:
    if duration_only(state, inputs, parameters) is False:
        return False


def upstream_parameters_only(state, inputs, parameters) -> bool:
    if duration_only(state, inputs, parameters) is False:
        return False


def all_inputs(state, inputs, parameters) -> bool:
    if duration_only(state, inputs, parameters) is False:
        return False


def partial_inputs_only(state, inputs, parameters) -> bool:
    if duration_only(state, inputs, parameters) is False:
        return False
