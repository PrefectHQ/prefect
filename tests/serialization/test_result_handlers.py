from prefect.engine.result_handlers import ResultHandler
from prefect.serialization.result_handlers import ResultHandlerSchema


# def test_all_states_have_serialization_schemas_in_stateschema():
#    """
#    Tests that all State subclasses in prefect.engine.states have corresponding schemas
#    in prefect.serialization.state
#    """
#    assert set(s.__name__ for s in all_states) == set(StateSchema.type_schemas.keys())
#
#
# def test_all_states_have_deserialization_schemas_in_stateschema():
#    """
#    Tests that all State subclasses in prefect.engine.states have corresponding schemas
#    in prefect.serialization.state with that state assigned as the object class
#    so it will be recreated at deserialization
#    """
#    assert set(all_states) == set(
#        s.Meta.object_class for s in StateSchema.type_schemas.values()
#    )


def test_serialize_base_result_handler():
    serialized = ResultHandlerSchema().dump(ResultHandler())
    assert isinstance(serialized, dict)
    assert serialized["type"] == "ResultHandler"


def test_deserialize_base_result_handler():
    schema = ResultHandlerSchema()
    obj = schema.load(schema.dump(ResultHandler()))
    assert isinstance(obj, ResultHandler)
    assert hasattr(obj, "logger")
    assert obj.logger.name == "prefect.ResultHandler"
