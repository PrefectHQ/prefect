# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/beta-eula


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


class AuthorizationError(PrefectError):
    pass
