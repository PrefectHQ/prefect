from collections import defaultdict
from itertools import product


_REGISTERED_POLICIES = []
POLICY_RULES = defaultdict(list)


def register(orchestration_rule):
    _REGISTERED_POLICIES.append(orchestration_rule)
    for transition in product(
        orchestration_rule.FROM_STATES, orchestration_rule.TO_STATES
    ):
        POLICY_RULES[tuple(transition)].append(orchestration_rule)
    return orchestration_rule


def lookup_transition_rules(from_state=None, to_state=None):
    from prefect.orion.orchestration import rule_priority
    priority = rule_priority.POLICY_PRIORITY
    transition_rules = POLICY_RULES[(from_state, to_state)]
    return list(sorted(transition_rules, key=lambda rule: priority.index(rule)))

