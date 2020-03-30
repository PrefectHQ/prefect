# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license


from typing import Optional

from graphql import GraphQLError


class PrefectServerException(Exception):
    pass


class NotFound(PrefectServerException):
    pass


class ApolloError(GraphQLError):
    """
    Apollo Server-style GraphQL Error
    """

    # the ApolloError's code, which is reported in its output
    code: Optional[str] = None
    # the ApolloError's default message
    message: Optional[str] = None

    def __init__(self, message: str = None, *args, **kwargs):
        if message is None:
            message = self.message

        super().__init__(message=message or "", *args, **kwargs)

        if self.code is not None:
            self.extensions["code"] = self.code


class Unauthenticated(ApolloError):
    code = "UNAUTHENTICATED"
    message = "Unauthenticated"


class Unauthorized(ApolloError):
    code = "FORBIDDEN"
    message = "Unauthorized"
