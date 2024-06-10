"""
Module for easily accessing dynamic attributes for a given run, especially those generated from deployments.

Example usage:
    ```python
    from prefect.runtime import deployment

    print(f"This script is running from deployment {deployment.id} with parameters {deployment.parameters}")
    ```
"""

import prefect.runtime.deployment
import prefect.runtime.flow_run
import prefect.runtime.task_run
