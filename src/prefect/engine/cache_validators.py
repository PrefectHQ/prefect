"""
Cache validators are functions that determine if a task's output cache
is still valid, or whether that task should be re-run.

A cache validator returns True if the cache is still valid, and False otherwise.
"""
from datetime import datetime, timedelta
from toolz import curry
from typing import TYPE_CHECKING, Dict, Iterable


def never_use(state, inputs, parameters) -> bool:
    return False


def duration_only(state, inputs, parameters) -> bool:
    if state.cached_result_expiration is None:
        return True
    elif state.cached_result_expiration > datetime.utcnow():
        return True
    else:
        return False


def all_inputs(state, inputs, parameters) -> bool:
    if duration_only(state, inputs, parameters) is False:
        return False
    elif state.cached_inputs == inputs:
        return True
    else:
        return False


def all_parameters(state, inputs, parameters) -> bool:
    if duration_only(state, inputs, parameters) is False:
        return False
    elif state.cached_parameters == parameters:
        return True
    else:
        return False


@curry
def partial_parameters_only(state, inputs, parameters, validate_on=None) -> bool:
    parameters = parameters or {}
    if duration_only(state, inputs, parameters) is False:
        return False
    elif validate_on is None:
        return True  # if you dont want to validate on anything, then the cache is valid
    else:
        cached = state.cached_parameters or {}
        partial_provided = {
            key: value for key, value in parameters.items() if key in validate_on
        }
        partial_needed = {
            key: value for key, value in cached.items() if key in validate_on
        }
        return partial_provided == partial_needed


@curry
def partial_inputs_only(state, inputs, parameters, validate_on=None) -> bool:
    inputs = inputs or {}
    if duration_only(state, inputs, parameters) is False:
        return False
    elif validate_on is None:
        return True  # if you dont want to validate on anything, then the cache is valid
    else:
        cached = state.cached_inputs or {}
        partial_provided = {
            key: value for key, value in inputs.items() if key in validate_on
        }
        partial_needed = {
            key: value for key, value in cached.items() if key in validate_on
        }
        return partial_provided == partial_needed
