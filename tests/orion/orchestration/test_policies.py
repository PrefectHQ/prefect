from prefect.orion.orchestration import core_policy, global_policy
from prefect.orion.orchestration import rule_priority


def test_all_rules_in_core_policy_are_prioritized():
    prioritized_policies = set(rule_priority.POLICY_PRIORITY)
    registered_policies = set(core_policy._REGISTERED_POLICIES)
    assert prioritized_policies == registered_policies
