# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license


"""
This module requires graphql-core-next
"""

from typing import Any, Dict, List

import ariadne
import graphql

import prefect_server
from prefect.utilities.graphql import parse_graphql, with_args
from prefect_server.utilities.graphql import GraphQLClient


class GraphQLRequest:
    def __init__(self, document, variables):
        self.document = document
        self.variables = variables


def make_remote_executable_schema(url: str) -> graphql.GraphQLSchema:
    """
    Creates an executable GraphQL schema from a remote endpoint.
    """
    client = GraphQLClient(url=url)

    introspection_result = client.execute(graphql.get_introspection_query())
    schema = graphql.build_client_schema(introspection_result.data)

    def root_resolver(obj, info, **inputs):
        query = graphql.print_ast(info.operation)
        # TODO: add graphql context
        delegated_result = client.execute(query=query, variables=info.variable_values)
        return delegated_result.data[info.field_name]

    # apply root resolver to any field on query or mutation roots
    resolvers = {
        schema.query_type.name: {q: root_resolver for q in schema.query_type.fields},
        schema.mutation_type.name: {
            q: root_resolver for q in schema.mutation_type.fields
        },
    }

    ariadne.resolvers.add_resolve_functions_to_schema(schema, resolvers)

    return schema


def delegate_to_schema(
    schema: graphql.GraphQLSchema,
    operation: str,
    field_name: str,
    args: dict,
    info: graphql.GraphQLResolveInfo,
):
    """
    Delegates a GraphQL Query to a different executable schema.

    https://github.com/apollographql/graphql-tools/blob/d3cbefc6b8a432c5b22f1ce25e56757ef03f4227/src/stitching/delegateToSchema.ts#L36

    Args:
        - schema (graphql.GraphQLSchema): an executable GraphQLSchema
        - operation (str): one of 'query', 'mutation', or 'subscription' indicating the operation type
        - field_name (str): the root field we are delegating to
        - args (dict): any input arguments for the field
        - info (graphql.GraphQLResolveInfo): the info object containing details about the request
    """

    document = create_document(
        target_field=field_name,
        target_operation=getattr(graphql.OperationType, operation.upper()),
        original_selections=info.field_nodes,
        fragments=list(info.fragments.values()),
        variables=info.operation.variable_definitions,
        operation_name=info.operation.name,
    )

    request = add_variables_to_root_field(schema=schema, document=document, args=args)
    result = graphql.execute(
        schema, document=request.document, variable_values=request.variables
    )
    return result


def create_document(
    target_field: str,
    target_operation: str,
    original_selections: List[graphql.SelectionNode],
    fragments: List[graphql.FragmentDefinitionNode],
    variables: List[graphql.VariableDefinitionNode],
    operation_name: graphql.NameNode,
) -> graphql.DocumentNode:
    """
    https://github.com/apollographql/graphql-tools/blob/d3cbefc6b8a432c5b22f1ce25e56757ef03f4227/src/stitching/delegateToSchema.ts#L139
    """

    selections: List[graphql.SelectionNode] = []
    args: List[graphql.ArgumentNode] = []

    for field in original_selections:
        selections.extend(getattr(field.selection_set, "selections", []))
        args.extend(field.arguments or [])

    if selections:
        selection_set = graphql.SelectionSetNode(selections=selections)
    else:
        selection_set = None

    root_field = graphql.FieldNode(
        alias=None,
        arguments=args,
        selection_set=selection_set,
        name=graphql.NameNode(value=target_field),
    )

    root_selection_set = graphql.SelectionSetNode(selections=[root_field])

    operation_definition = graphql.OperationDefinitionNode(
        operation=target_operation,
        variable_definitions=variables,
        selection_set=root_selection_set,
        name=operation_name,
    )

    return graphql.DocumentNode(definitions=[operation_definition, *fragments])


def add_variables_to_root_field(
    schema: graphql.GraphQLSchema, document: graphql.DocumentNode, args: Dict[str, Any]
) -> GraphQLRequest:
    """
    https://github.com/apollographql/graphql-tools/blob/0046a0e3bf2a120a59e4f4e392d4ddc3728e4f3c/src/transforms/AddArgumentsAsVariables.ts#L47
    """

    operations = [d for d in document.definitions if d.kind == "operation_definition"]
    fragments = [d for d in document.definitions if d.kind == "fragment_definition"]

    variable_names = {}

    for operation in operations:
        existing_variables = set(
            v.variable.name.value for v in operation.variable_definitions
        )
        variable_counter = 0
        variables = {}

        def generate_variable_name(arg_name: str) -> str:
            nonlocal variable_counter
            variable_name = f"_v{variable_counter}_{arg_name}"
            while variable_name in existing_variables:
                variable_counter += 1
                variable_name = f"_v{variable_counter}_{arg_name}"
            return variable_name

        if operation.operation == operation.operation.SUBSCRIPTION:
            op_type = schema.subscription_type
        elif operation.operation == operation.operation.MUTATION:
            op_type = schema.mutation_type
        elif operation.operation == operation.operation.QUERY:
            op_type = schema.query_type
        else:
            raise ValueError("Unexpected operation.")

        if not op_type:
            continue

        new_selection_set = []

        for selection in operation.selection_set.selections:
            if selection.kind == "field":
                new_args = {arg.name.value: arg for arg in selection.arguments}
                name = selection.name.value
                field = op_type.fields[name]
                for argument_name, argument in field.args.items():
                    if argument_name in args:
                        variable_name = generate_variable_name(argument_name)
                        variable_names[argument_name] = variable_name
                        new_args[argument_name] = graphql.ArgumentNode(
                            name=graphql.NameNode(value=argument_name),
                            value=graphql.VariableNode(
                                name=graphql.NameNode(value=variable_name)
                            ),
                        )
                        existing_variables.add(variable_name)
                        variables[variable_name] = graphql.VariableDefinitionNode(
                            variable=graphql.VariableNode(
                                name=graphql.NameNode(value=variable_name)
                            ),
                            type=type_to_ast(graphql_type=argument.type),
                        )
                selection.arguments = list(new_args.values())
            new_selection_set.append(selection)

        operation.variable_definitions.extend(variables.values())
        operation.selection_set = graphql.SelectionSetNode(selections=new_selection_set)

    new_variables = {variable_names[name]: args[name] for name in variable_names}

    new_document = graphql.DocumentNode(definitions=operations + fragments)
    return GraphQLRequest(document=document, variables=new_variables)


def type_to_ast(graphql_type):
    """
    https://github.com/apollographql/graphql-tools/blob/0046a0e3bf2a120a59e4f4e392d4ddc3728e4f3c/src/transforms/AddArgumentsAsVariables.ts#L171
    """
    if isinstance(graphql_type, graphql.GraphQLNonNull):
        inner_type = type_to_ast(graphql_type.of_type)
        if inner_type.kind in ("list_type", "named_type"):
            return graphql.NonNullTypeNode(type=inner_type)
        else:
            raise ValueError("Incorrect inner non-null type.")

    elif isinstance(graphql_type, graphql.GraphQLList):
        return graphql.ListTypeNode(type=type_to_ast(graphql_type.of_type))
    else:
        return graphql.NamedTypeNode(name=graphql.NameNode(value=str(graphql_type)))
