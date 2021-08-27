from prefect.orion.orchestration import rules

POLICY_PRIORITY = [
    rules.RetryPotentialFailures,
    rules.CacheInsertion,
    rules.CacheRetrieval,
]
