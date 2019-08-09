from prefect.agent.agent import Agent

try:
    import prefect.agent.kubernetes
except ImportError:
    raise ImportError(
        'Using `prefect.agent.kubernetes` requires Prefect to be installed with the "kubernetes" extra.'
    )

import prefect.agent.local
import prefect.agent.nomad
