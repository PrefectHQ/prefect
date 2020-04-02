# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license


import ujson
import datetime
import uuid
from typing import List, Union, cast

import pendulum
from box import Box

import psycopg2
import prefect
from prefect.utilities.graphql import with_args
from prefect_server import config
from prefect_server.database.hasura import GQLObjectTypes, HasuraClient
import pydantic

hasura_client = HasuraClient()
sentinel = object()

UUIDString = pydantic.constr(
    regex=r"[0-9a-fA-F]{8}\-[0-9a-fA-F]{4}\-[0-9a-fA-F]{4}\-[0-9a-fA-F]{4}\-[0-9a-fA-F]{12}"
)

pydantic.json.ENCODERS_BY_TYPE[pendulum.DateTime] = str
pydantic.json.ENCODERS_BY_TYPE[pendulum.Date] = str
pydantic.json.ENCODERS_BY_TYPE[pendulum.Time] = str
pydantic.json.ENCODERS_BY_TYPE[pendulum.Duration] = lambda x: str(x.total_seconds())
pydantic.json.ENCODERS_BY_TYPE[pendulum.Period] = lambda x: str(x.total_seconds())
pydantic.json.ENCODERS_BY_TYPE[prefect.engine.result.NoResultType] = str


def _as_pendulum(value: Union[str, datetime.datetime]) -> pendulum.DateTime:
    if isinstance(value, datetime.datetime):
        return pendulum.instance(value).in_tz("UTC")
    else:
        return pendulum.parse(value).in_tz("UTC")


def _as_timedelta(value: Union[str, datetime.timedelta]) -> datetime.timedelta:
    if isinstance(value, str):
        # try as a postgres "english" interval literal, which could include colon-delimited time
        if " " in value:
            value = psycopg2.extensions.PYINTERVAL(value, None)
        # try as a colon-delimited string
        elif ":" in value:
            H, M, S = value.split(":")
            value = datetime.timedelta(
                hours=float(H), minutes=float(M), seconds=float(S)
            )
        # try as a float of seconds
        else:
            value = datetime.timedelta(seconds=float(value))
    return value


class HasuraModel(pydantic.BaseModel):
    """
    An ORM class for working with Hasura objects
    """

    __hasura_type__ = ""

    def __repr_args__(self) -> List:
        """
        Modified pydantic repr to only include set fields
        """
        return [(k, v) for k, v in self.__dict__.items() if k in self.__fields_set__]

    @pydantic.root_validator(pre=True)
    def _convert_types(cls, model_values: dict) -> dict:
        """
        A globally-applied validator that:
            - converts datetimes to pendulum instances
            - converts postgres intervals (H:M:S or literal english) to timedeltas
        """
        for field_name, field_value in list(model_values.items()):
            field = cast(pydantic.fields.Field, cls.__fields__.get(field_name))
            # check if the field value is a datetime
            if (
                field is None
                or field_value is None
                or not isinstance(field.type_, type)
            ):
                continue

            # convert datetimes to pendulum.DateTime in UTC
            if issubclass(field.type_, datetime.datetime):
                if field.shape == 1:
                    model_values[field_name] = _as_pendulum(field_value)
                else:
                    model_values[field_name] = type(field_value)(
                        _as_pendulum(v) for v in field_value
                    )

            # convert timedeltas in H:M:S or postgres format to timedeltas
            elif issubclass(field.type_, datetime.timedelta):
                if field.shape == 1:
                    model_values[field_name] = _as_timedelta(field_value)
                else:
                    model_values[field_name] = type(field_value)(
                        _as_timedelta(v) for v in field_value
                    )

        return model_values

    def dict(self, **kwargs) -> dict:
        kwargs.setdefault("exclude_unset", True)
        return super().dict(**kwargs)

    def json(self, **kwargs) -> dict:
        kwargs.setdefault("exclude_unset", True)
        return super().json(**kwargs)

    def to_hasura_dict(self, is_insert: bool = False, **kwargs) -> dict:
        data = ujson.loads(self.json(**kwargs))
        data = self._format_hasura_dict(data, is_insert=is_insert)
        return data

    @classmethod
    def _format_hasura_dict(cls, data: dict, is_insert: bool = False) -> dict:
        """
        Formats data for Hasura:
            - adds `data` keys for inserts
            - converts `Intervals` to strings

        Args:
            - data (dict): a data dictionary, as output from HasuraModel.dict()

        Returns:
            - dict: the formatted data dictionary
        """
        for field_name, field_value in list(data.items()):
            field = cls.__fields__.get(field_name)
            if not field or field_value is None:
                continue

            # handle `data` key on insert
            elif isinstance(field.type_, type) and issubclass(field.type_, HasuraModel):

                # if the shape is 1 it indicates pydantic.fields.SHAPE_SINGLETON, meaning
                # not a container type
                if field.shape == 1:
                    field_value = field.type_._format_hasura_dict(
                        field_value, is_insert=is_insert
                    )
                    if is_insert:
                        field_value = dict(data=field_value)
                else:
                    field_value = [
                        field.type_._format_hasura_dict(v, is_insert=is_insert)
                        for v in field_value
                    ]
                    if is_insert:
                        field_value = dict(data=field_value)

            elif isinstance(field.type_, type) and issubclass(
                field.type_, datetime.timedelta
            ):

                if field.shape == 1:
                    field_value = str(field_value)
                else:
                    field_value = [str(v) for v in field_value]

            data[field_name] = field_value
        return data

    async def insert(
        self,
        on_conflict: GQLObjectTypes = None,
        selection_set: GQLObjectTypes = None,
        alias: str = None,
        run_mutation: bool = True,
    ) -> dict:
        """
        Insert this object into the database, automatically adding an ID if not provided.

        Note that this method applies the Marshmallow schema. To avoid applying a schema,
        use `insert_many`.

        Args:
            - on_conflict (GQLObjectTypes): a Hasura on_conflict clause
            - selection_set (GQLObjectTypes): a hasura selection_set. If None,
                a list of ids will be returned.
            - alias (str): a GraphQL alias, useful when running this mutation in a batch.
            - run_mutation (bool): if True (default), the mutation is run immediately. If False,
                an object is returned that can be passed to `HasuraClient.execute_mutations_in_transaction`.

        Returns:
            - dict: the values in the `selection_set`
        """
        if selection_set is None:
            return_id = True
            selection_set = {"returning": "id"}
        else:
            return_id = False

        result = await hasura_client.insert(
            graphql_type=self.__hasura_type__,
            objects=[self.to_hasura_dict(is_insert=True)],
            on_conflict=on_conflict,
            selection_set=selection_set,
            alias=alias,
            run_mutation=run_mutation,
        )

        if run_mutation:
            # since there is only one insert, we can replace the list with the first item
            if "returning" in result:
                result["returning"] = result["returning"][0]
            if return_id:
                return result["returning"]["id"]
        return result

    async def delete(
        self,
        selection_set: GQLObjectTypes = None,
        alias: str = None,
        run_mutation: bool = True,
    ) -> dict:
        """
        Delete this object from the database

        Args:
            - selection_set (GQLObjectTypes): a hasura selection_set. If None,
                a list of ids will be returned.
            - alias (str): a GraphQL alias, useful when running this mutation in a batch.
            - run_mutation (bool): if True (default), the mutation is run immediately. If False,
                an object is returned that can be passed to `HasuraClient.execute_mutations_in_transaction`.

        Returns:
            - dict: the fields in the `selection_set`
        """

        if not hasattr(self, "id"):
            raise ValueError("This instance has no ID; can not delete.")

        if selection_set is None:
            check_result = True
            selection_set = "affected_rows"
        else:
            check_result = False

        result = await hasura_client.delete(
            graphql_type=self.__hasura_type__,
            id=str(self.id) if isinstance(self.id, uuid.UUID) else self.id,
            selection_set=selection_set,
            alias=alias,
            run_mutation=run_mutation,
        )

        if run_mutation and check_result:
            return result.affected_rows == 1
        return result

    @classmethod
    async def insert_many(
        cls,
        objects: List[Union[dict, "HasuraModel"]],
        on_conflict: GQLObjectTypes = None,
        selection_set: GQLObjectTypes = None,
        alias: str = None,
        run_mutation: bool = True,
    ) -> dict:
        """
        Inserts a list of objects into the database.

        Args:
            - objects (List[dict]): the objects to insert into the database
            - on_conflict (GQLObjectTypes): a Hasura on_conflict clause
            - selection_set (GQLObjectTypes): a hasura selection_set. If None,
                a list of ids will be returned.
            - alias (str): a GraphQL alias, useful when running this mutation in a batch.
            - run_mutation (bool): if True (default), the mutation is run immediately. If False,
                an object is returned that can be passed to `HasuraClient.execute_mutations_in_transaction`.

        Returns:
            - dict: the fields in the `selection_set`
        """

        if selection_set is None:
            return_id = True
            selection_set = {"returning": "id"}
        else:
            return_id = False

        validated_objects = []
        for obj in objects:
            if not isinstance(obj, cls):
                obj = cls(**obj)
            validated_objects.append(obj.to_hasura_dict(is_insert=True))

        result = await hasura_client.insert(
            graphql_type=cls.__hasura_type__,
            objects=validated_objects,
            on_conflict=on_conflict,
            selection_set=selection_set,
            alias=alias,
            run_mutation=run_mutation,
        )
        if run_mutation and return_id:
            return [r["id"] for r in result["returning"]]
        return result

    @classmethod
    async def exists(cls, id: str) -> bool:
        """
        Returns True if an object with the specified ID exists in the database; False otherwise.

        Args:
            - id (str): an object with this ID will be tested

        Returns:
            - bool: True if the object exists; False otherwise
        """
        if isinstance(id, uuid.UUID):
            id = str(id)
        return await hasura_client.exists(graphql_type=cls.__hasura_type__, id=id)

    @classmethod
    def where(cls, where: GQLObjectTypes = None, id: str = sentinel) -> "ModelQuery":
        """
        Constructs a "where" clause for this object type, allowing mutations like `update` and
        `delete`, as well as queries for multiple objects.

        Args:
            - where (GQLObjectTypes): a Hasura where clause. If None, will select all objects.
            - id (str): an optional ID that will be added to the where clause as:
                `{"id": {"_eq": id}}`


        Returns:
            - ModelQuery: a ModelQuery object allowing bulk mutations
        """
        where = where or {}
        if isinstance(id, uuid.UUID):
            id = str(id)

        # check if the ID was passed as "None", because this tells Hasura to ignore the
        # filter and query EVERYTHING.
        if id is None:
            raise ValueError(
                "The provided id was `None`, which tells Hasura to ignore the filter."
            )
        # otherwise check if an ID was provided
        elif id is not sentinel:
            where.update({"id": {"_eq": id}})
        return ModelQuery(model=cls, where=where)


class ModelQuery:
    """
    A class for performing queries across multiple models at once.

    ModelQuery objects store a parent `model` as well as a `where` clause,
    and allow updates / deletes / queries to be performed across all matching
    objects.

    Args:
        - model (HasuraModel): the model class to query
        - where (dict): a Hasura where claus
    """

    def __init__(self, model: HasuraModel, where: dict = None):
        self.model = model
        self.where = where

    async def update(
        self,
        set: GQLObjectTypes = None,
        increment: GQLObjectTypes = None,
        selection_set: GQLObjectTypes = None,
        alias: str = None,
        run_mutation: bool = True,
    ) -> dict:
        """
        Updates objects corresponding to the query's where clause.

        Args:
            - set (GQLObjectTypes): a Hasura `_set` clause
            - increment (GQLObjectTypes): a Hasura `_increment` clause
            - selection_set (GQLObjectTypes): a hasura selection_set. If None,
                a list of ids will be returned.
            - alias (str): a GraphQL alias, useful when running this mutation in a batch.
            - run_mutation (bool): if True (default), the mutation is run immediately. If False,
                an object is returned that can be passed to `HasuraClient.execute_mutations_in_transaction`.

        Returns:
            - dict: the fields in the `selection_set`
        """
        if set is not None:
            set = self.model(**set).to_hasura_dict()
        else:
            set = {}

        result = await hasura_client.update(
            graphql_type=self.model.__hasura_type__,
            where=self.where,
            set=set,
            increment=increment,
            selection_set=selection_set,
            alias=alias,
            run_mutation=run_mutation,
        )
        return result

    async def delete(
        self,
        selection_set: GQLObjectTypes = None,
        alias: str = None,
        run_mutation: bool = True,
    ) -> dict:
        """
        Deletes objects corresponding to the query's where clause.

        Args:
            - selection_set (GQLObjectTypes): a hasura selection_set. If None,
                a list of ids will be returned.
            - alias (str): a GraphQL alias, useful when running this mutation in a batch.
            - run_mutation (bool): if True (default), the mutation is run immediately. If False,
                an object is returned that can be passed to `HasuraClient.execute_mutations_in_transaction`.

        Returns:
            - dict: the fields in the `selection_set`
        """

        result = await hasura_client.delete(
            graphql_type=self.model.__hasura_type__,
            where=self.where,
            selection_set=selection_set,
            alias=alias,
            run_mutation=run_mutation,
        )

        return result

    async def get(
        self,
        selection_set: GQLObjectTypes = None,
        offset=None,
        limit=None,
        order_by=None,
        distinct_on=None,
        apply_schema: bool = True,
    ) -> List[HasuraModel]:
        """
        Gets `limit` objects corresponding to the query's where clause.

        Args:
            - selection_set (GQLObjectTypes): a hasura selection_set. If None,
                a list of ids will be returned.
            - limit (int): limits the number of objects that will be retrieved
            - offset (int): offsets the query by the specified amount
            - order_by (GQLObjectTypes): a Hasura `order_by` clause
            - distinct_on (GQLObjectTypes): a Hasura `distinct_on` clause
            - apply_schema (bool): if True, the result is an ORM model

        Returns:
            - dict: the fields in the `selection_set`
        """
        arguments = {}

        if selection_set is None:
            selection_set = "id"

        if self.where is not None:
            arguments["where"] = self.where
        if order_by is not None:
            arguments["order_by"] = order_by
        if distinct_on is not None:
            arguments["distinct_on"] = distinct_on
        if offset is not None:
            arguments["offset"] = offset
        if limit is not None:
            arguments["limit"] = limit

        obj = self.model.__hasura_type__
        if arguments:
            obj = with_args(self.model.__hasura_type__, arguments)

        result = await hasura_client.execute(
            query={"query": {obj: selection_set}},
            # if we are applying the schema, don't retrieve a box object
            # if we are NOT applying the schema, DO retrieve a box object
            as_box=not apply_schema,
        )
        data = result["data"][self.model.__hasura_type__]
        if apply_schema:
            return [self.model(**d) for d in data]
        else:
            return data

    async def first(
        self,
        selection_set: GQLObjectTypes = None,
        order_by: GQLObjectTypes = None,
        apply_schema: bool = True,
    ) -> HasuraModel:
        """
        Gets the first object corresponding to the query's where clause.

        Args:
            - selection_set (GQLObjectTypes): a hasura selection_set. If None,
                a list of ids will be returned.
            - order_by (GQLObjectTypes): a Hasura `order_by` clause
            - apply_schema (bool): if True, applies a Schema to deserialize results

        Returns:
            - dict: the fields in the `selection_set`
        """
        if selection_set is None:
            selection_set = "id"
        result = await self.get(
            selection_set=selection_set,
            limit=1,
            order_by=order_by,
            apply_schema=apply_schema,
        )
        if result:
            return result[0]

    async def count(self, distinct_on: List[str] = None,) -> int:
        """
        Counts the number of objects corresponding to the query's where clause.

        Please note that counting distinct items is a slow operation and should be avoided
        if possible, or paired with an appropriate `where` clause. Even indices may not
        help counting distinct items.

        Args:
            - distinct_on (List[str]): a Hasura `distinct_on` clause

        Returns:
            - int: the count of matching items
        """

        arguments = {"where": self.where or {}}
        if distinct_on is not None:
            arguments["distinct_on"] = distinct_on

        query = {
            "query": {
                with_args(
                    f"count_query: {self.model.__hasura_type__}_aggregate", arguments,
                ): {"aggregate": "count"}
            }
        }
        result = await hasura_client.execute(query, as_box=False)
        return result["data"]["count_query"]["aggregate"]["count"]

    async def max(self, columns) -> dict:
        """
        Returns the maximum value of the requested columns

        Args:

        Returns:
            - dict: the requested columns and corresponding minmums
        """
        query = {
            "query": {
                with_args(
                    f"max_query: {self.model.__hasura_type__}_aggregate",
                    {"where": self.where},
                ): {"aggregate": {"max": set(columns)}}
            }
        }
        result = await hasura_client.execute(query, as_box=False)
        return result["data"]["max_query"]["aggregate"]["max"]

    async def min(self, columns) -> dict:
        """
        Returns the minimum value of the requested columns

        Args:

        Returns:
            - dict: the requested columns and corresponding minmums
        """
        query = {
            "query": {
                with_args(
                    f"min_query: {self.model.__hasura_type__}_aggregate",
                    {"where": self.where},
                ): {"aggregate": {"min": set(columns)}}
            }
        }
        result = await hasura_client.execute(query, as_box=False)
        return result["data"]["min_query"]["aggregate"]["min"]
