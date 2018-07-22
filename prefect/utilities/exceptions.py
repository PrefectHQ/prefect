class PrefectError(Exception):
    pass


class ContextError(KeyError, PrefectError):
    pass


class SerializationError(PrefectError):
    pass
