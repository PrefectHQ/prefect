class PrefectError(Exception):
    pass


class ContextError(KeyError, PrefectError):
    pass


class SerializationError(PrefectError):
    pass


class PrefectWarning(UserWarning):
    pass


class ClientError(PrefectError):
    pass


class AuthorizationError(ClientError):
    pass


class StorageError(PrefectError):
    pass


class ExecutorError(PrefectError):
    pass


class ExecutorShutdown(ExecutorError):
    pass
