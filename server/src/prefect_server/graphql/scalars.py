# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license


import json
import uuid

import ariadne
import pendulum

import prefect_server

JSONScalar = ariadne.ScalarType("JSON")


@JSONScalar.serializer
def json_serializer(value):
    """
    JSON outputs are NOT serialized to string, but rather returned as JSON documents
    """
    return value


@JSONScalar.value_parser
def json_value_parser(value):
    """
    When a JSON value is passed as a variable, it's already in the correct JSON document form.
    """
    return value


@JSONScalar.literal_parser
def json_literal_parser(ast):
    """
    When a JSON scalar is passed as part of the literal query string, it needs to be loaded.
    """
    return json.loads(ast.value)


DateTimeScalar = ariadne.ScalarType("DateTime")


@DateTimeScalar.serializer
def datetime_serializer(value):
    """
    When a datetime is passed, it needs to be serialized to an iso-formatted string
    """
    return value.isoformat()


@DateTimeScalar.value_parser
def datetime_value_parser(value):
    """
    Parse datetime strings into datetime objects
    """
    return pendulum.parse(value)


@DateTimeScalar.literal_parser
def datetime_literal_parser(ast):
    """
    Parse datetime strings into datetime objects
    """
    return datetime_value_parser(ast.value)


UUIDScalar = ariadne.ScalarType("UUID")


@UUIDScalar.serializer
def uuid_serializer(value):
    return str(value)


@UUIDScalar.value_parser
def uuid_value_parser(value) -> str:
    """
    Ensure values are proper UUIDs
    """
    try:
        return str(uuid.UUID(value))
    except:
        raise ValueError("Could not parse UUID: {}".format(value))


@UUIDScalar.literal_parser
def uuid_literal_parser(ast):
    return uuid_value_parser(ast.value)


resolvers = [JSONScalar, DateTimeScalar, UUIDScalar]
