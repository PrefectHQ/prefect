# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

class PrefectError(Exception):
    pass


class ContextError(KeyError, PrefectError):
    pass


class SerializationError(PrefectError):
    pass
