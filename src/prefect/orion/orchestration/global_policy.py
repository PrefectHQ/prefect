from collections import defaultdict
from itertools import product


POLICY_RULES = defaultdict(list)


def register(orchestration_rule):
    for transition in product(orchestration_rule.FROM_STATES, orchestration_rule.TO_STATES):
        POLICY_RULES[tuple(transition)].append(orchestration_rule)
    return orchestration_rule


def transition_rules(from_state=None, to_state=None):
    return POLICY_RULES[(from_state, to_state)]
