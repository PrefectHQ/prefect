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


class VersionLockError(PrefectError):
    pass


class AuthorizationError(ClientError):
    pass


class StorageError(PrefectError):
    pass
