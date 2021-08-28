from prefect.orion.orchestration import core_policy, global_policy


def test_all_rules_in_core_policy_are_prioritized():
    policy = core_policy.CorePolicy
    prioritized_rules = set(policy.priority())
    registered_rules = set(policy.REGISTERED_RULES)
    assert prioritized_rules == registered_rules


def test_all_rules_in_global_policy_are_prioritized():
    policy = global_policy.GlobalPolicy
    prioritized_rules = set(policy.priority())
    registered_rules = set(policy.REGISTERED_RULES)
    assert prioritized_rules == registered_rules
