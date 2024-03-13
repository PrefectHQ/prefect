import pytest

from prefect.utilities.schema_tools.hydration import (
    HydrationContext,
    InvalidJSON,
    ValueNotFound,
    WorkspaceVariableNotFound,
    hydrate,
)


class TestHydratePassThrough:
    # Hydrating without a `__prefect_kind` should just leave
    # all the values as is.
    @pytest.mark.parametrize(
        "input_object",
        [
            # Simple pass-through cases
            ({"param": None}),
            ({"param": 10}),
            ({"param": "hello"}),
            ({"param": [1, 2, 3]}),
            ({"param": {"key": "value"}}),
            ({"param": {"value": 10}}),
            ({"param": {"value": "hello"}}),
            ({"param": {"value": [1, 2, 3]}}),
            ({"param": {"value": {"key": "value"}}}),
            # Nested object
            ({"value": {"nested": {"another_key": "another_value"}}},),
            # Cases where value is missing
            ({"param": {}}, {"param": {}}),
            ({}, {}),
        ],
    )
    def test_hydrate_basic(self, input_object):
        assert hydrate(input_object) == input_object

    def test_hydrate_unregistered_prefect_kind(self):
        """We pass through the `value` key of any unrecognized `__prefect_kind`."""
        assert (
            hydrate({"__prefect_kind": "never-heard-of-it", "value": "hello"})
            == "hello"
        )


class TestHydrateRaiseOnError:
    async def test_dont_raise_if_error(self):
        values = {"param": {"__prefect_kind": "none"}}

        res = hydrate(values, ctx=HydrationContext(raise_on_error=False))
        assert res == {"param": ValueNotFound()}

    async def test_raise_if_error(self):
        values = {"param": {"__prefect_kind": "none"}}

        with pytest.raises(ValueNotFound) as exc:
            hydrate(values, ctx=HydrationContext(raise_on_error=True))
        assert str(exc.value) == "Missing 'value' key in __prefect object"

    async def test_dont_raise_if_no_error(self):
        values = {"param": {"__prefect_kind": "none", "value": "5"}}

        hydrate(values, ctx=HydrationContext(raise_on_error=False))


class TestHydrateWithNonePrefectKind:
    @pytest.mark.parametrize(
        "input_object, expected_output",
        [
            # __prefect_kind set to None, should be a simple pass-through
            ({"param": {"__prefect_kind": "none", "value": None}}, {"param": None}),
            ({"param": {"__prefect_kind": "none", "value": 10}}, {"param": 10}),
            (
                {"param": {"__prefect_kind": "none", "value": "hello"}},
                {"param": "hello"},
            ),
            (
                {"param": {"__prefect_kind": "none", "value": [1, 2, 3]}},
                {"param": [1, 2, 3]},
            ),
            (
                {"param": {"__prefect_kind": "none", "value": {"key": "value"}}},
                {"param": {"key": "value"}},
            ),
            # Complex objects with __prefect_kind set to "none"
            (
                {
                    "param": {
                        "__prefect_kind": "none",
                        "value": {"nested": {"another_key": "another_value"}},
                    }
                },
                {"param": {"nested": {"another_key": "another_value"}}},
            ),
            # Nested "none" __prefect_kinds
            (
                {
                    "param": {
                        "__prefect_kind": "none",
                        "value": {
                            "hello": "world",
                            "goodbye": {"__prefect_kind": "none", "value": "moon"},
                        },
                    }
                },
                {"param": {"hello": "world", "goodbye": "moon"}},
            ),
            ({"param": {"__prefect_kind": "none"}}, {"param": ValueNotFound()}),
        ],
    )
    def test_hydrate_with_null_prefect_kind(self, input_object, expected_output):
        assert hydrate(input_object) == expected_output


class TestHydrateWithJsonPrefectKind:
    @pytest.mark.parametrize(
        "input_object, expected_output",
        [
            # __prefect_kind set to "json", JSON string should be parsed
            (
                {"param": {"__prefect_kind": "json", "value": '{"key": "value"}'}},
                {"param": {"key": "value"}},
            ),
            (
                {
                    "param": {
                        "__prefect_kind": "json",
                        "value": '{"nested": {"another_key": "another_value"}}',
                    }
                },
                {"param": {"nested": {"another_key": "another_value"}}},
            ),
            # JSON string with line breaks and formatting
            (
                {
                    "param": {
                        "__prefect_kind": "json",
                        "value": '{\n  "key": "value",\n  "nested": {\n    "another_key": "another_value"\n  }\n}',
                    }
                },
                {"param": {"key": "value", "nested": {"another_key": "another_value"}}},
            ),
            # JSON string containing `__prefect_kind` which should be treated as a regular field
            (
                {
                    "param": {
                        "__prefect_kind": "json",
                        "value": '{"__prefect_kind": "some_value", "key": "value"}',
                    }
                },
                {"param": {"__prefect_kind": "some_value", "key": "value"}},
            ),
            # Invalid JSON
            (
                {
                    "param": {
                        "__prefect_kind": "json",
                        "value": '{"key": unquotedvalue}',
                    }
                },
                {
                    "param": InvalidJSON(
                        detail="Expecting value: line 1 column 9 (char 8)"
                    )
                },
            ),
            # Cases where __prefect_kind is "json", but value is missing
            ({"param": {"__prefect_kind": "json"}}, {}),
            ({"__prefect_kind": "json"}, {}),
        ],
    )
    def test_hydrate_with_json_prefect_kind(self, input_object, expected_output):
        assert hydrate(input_object) == expected_output


class TestHydrateWithWorkspaceVariablePrefectKind:
    @pytest.mark.parametrize(
        "input_object, expected_output, ctx",
        [
            # Cases where __prefect_kind is "workspace_variable",
            # but "variable_name"" is missing
            (
                {"param": {"__prefect_kind": "workspace_variable"}},
                {},
                HydrationContext(),
            ),
            ({"__prefect_kind": "workspace_variable"}, {}, HydrationContext()),
            # variable not found in context
            (
                {
                    "param": {
                        "__prefect_kind": "workspace_variable",
                        "variable_name": "my-var",
                    }
                },
                {"param": WorkspaceVariableNotFound("my-var")},
                HydrationContext(),
            ),
            # variable exists in context
            (
                {
                    "param": {
                        "__prefect_kind": "workspace_variable",
                        "variable_name": "my-var",
                    }
                },
                {"param": "my-value"},
                HydrationContext(workspace_variables={"my-var": "my-value"}),
            ),
        ],
    )
    def test_hydrate_with_null_prefect_kind(self, input_object, expected_output, ctx):
        assert hydrate(input_object, ctx) == expected_output
