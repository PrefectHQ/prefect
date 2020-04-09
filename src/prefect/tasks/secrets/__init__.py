"""
Secret Tasks are a special kind of Prefect Task used to represent the retrieval of sensitive data.

The base implementation uses Prefect Cloud secrets, but users are encouraged to subclass the `Secret` task
class for interacting with other secret providers. Secrets always use a special kind of result handler that
prevents the persistence of sensitive information.
"""
from .base import SecretBase, PrefectSecret, Secret
from .env_var import EnvVarSecret
