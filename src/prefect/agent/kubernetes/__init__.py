try:
    from prefect.agent.kubernetes.agent import KubernetesAgent
    from prefect.agent.kubernetes.resource_manager import ResourceManager
except ImportError:
    raise ImportError(
        'Using `prefect.agent.kubernetes` requires Prefect to be installed with the "kubernetes" extra.'
    )
