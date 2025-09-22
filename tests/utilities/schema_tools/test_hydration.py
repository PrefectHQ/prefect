import pytest

from prefect.utilities.schema_tools.hydration import (
    HydrationContext,
    InvalidJinja,
    InvalidJSON,
    TemplateNotFound,
    ValidJinja,
    ValueNotFound,
    WorkspaceVariable,
    WorkspaceVariableNotFound,
    _coerce_jinja_result,
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
            (
                {"param": {"__prefect_kind": "json", "value": 12346}},
                {
                    "param": InvalidJSON(
                        detail="the JSON object must be str, bytes or bytearray, not int"
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


class TestCoerceJinjaResult:
    """Test the type coercion functionality for Jinja template results."""

    def test_coerce_integers(self):
        assert _coerce_jinja_result("42") == 42
        assert isinstance(_coerce_jinja_result("42"), int)
        assert _coerce_jinja_result("-42") == -42
        assert isinstance(_coerce_jinja_result("-42"), int)
        assert _coerce_jinja_result("0") == 0
        assert isinstance(_coerce_jinja_result("0"), int)

    def test_coerce_floats(self):
        assert _coerce_jinja_result("3.14") == 3.14
        assert isinstance(_coerce_jinja_result("3.14"), float)
        assert _coerce_jinja_result("-3.14") == -3.14
        assert isinstance(_coerce_jinja_result("-3.14"), float)
        assert _coerce_jinja_result("0.0") == 0.0
        assert isinstance(_coerce_jinja_result("0.0"), float)

    def test_coerce_whitespace_handling(self):
        assert _coerce_jinja_result("  42  ") == 42
        assert isinstance(_coerce_jinja_result("  42  "), int)
        assert _coerce_jinja_result("  3.14  ") == 3.14
        assert isinstance(_coerce_jinja_result("  3.14  "), float)
        # Non-numeric strings with whitespace preserve their formatting
        assert _coerce_jinja_result("  hello  ") == "  hello  "
        assert isinstance(_coerce_jinja_result("  hello  "), str)

    def test_coerce_non_numeric_strings(self):
        assert _coerce_jinja_result("hello") == "hello"
        assert isinstance(_coerce_jinja_result("hello"), str)
        assert _coerce_jinja_result("not-a-number") == "not-a-number"
        assert isinstance(_coerce_jinja_result("not-a-number"), str)
        assert _coerce_jinja_result("42.5.5") == "42.5.5"  # Invalid float
        assert isinstance(_coerce_jinja_result("42.5.5"), str)

    def test_coerce_edge_cases(self):
        # Empty string stays string
        assert _coerce_jinja_result("") == ""
        assert isinstance(_coerce_jinja_result(""), str)

        # Scientific notation
        assert _coerce_jinja_result("1e5") == 100000.0
        assert isinstance(_coerce_jinja_result("1e5"), float)

        # Hexadecimal - should stay as string since we're not trying to parse it
        assert _coerce_jinja_result("0x10") == "0x10"
        assert isinstance(_coerce_jinja_result("0x10"), str)

        # JSON strings should not be coerced
        assert _coerce_jinja_result('"4"') == '"4"'
        assert isinstance(_coerce_jinja_result('"4"'), str)
        assert _coerce_jinja_result('{"key": "value"}') == '{"key": "value"}'
        assert isinstance(_coerce_jinja_result('{"key": "value"}'), str)
        assert _coerce_jinja_result("[1, 2, 3]") == "[1, 2, 3]"
        assert isinstance(_coerce_jinja_result("[1, 2, 3]"), str)


class TestHydrateWithJinjaPrefectKind:
    @pytest.mark.parametrize(
        "input_object, expected_output",
        [
            # Valid Jinja template
            (
                {"param": {"__prefect_kind": "jinja", "template": "Hello {{ name }}"}},
                {"param": ValidJinja("Hello {{ name }}")},
            ),
            # Jinja template with syntax error
            (
                {"param": {"__prefect_kind": "jinja", "template": "Hello {{ name"}},
                {
                    "param": InvalidJinja(
                        "unexpected end of template, expected 'end of print statement'."
                    )
                },
            ),
            # Security error in Jinja template
            (
                {
                    "param": {
                        "__prefect_kind": "jinja",
                        "template": """
                        {% for i in range(1) %}
                            Level 1
                            {% for j in range(1) %}
                                Level 2
                                    {% for k in range(1) %}
                                        Level 3
                                    {% endfor %}
                            {% endfor %}
                        {% endfor %}
                        """,
                    }
                },
                {
                    "param": InvalidJinja(
                        "Contains nested for loops at a depth of 3. Templates can nest for loops no more than 2 loops deep."
                    )
                },
            ),
            # Missing template
            (
                {"param": {"__prefect_kind": "jinja"}},
                {"param": TemplateNotFound()},
            ),
        ],
    )
    def test_hydrate_with_jinja_prefect_kind(self, input_object, expected_output):
        assert hydrate(input_object) == expected_output

    def test_render_jinja(self):
        values = {"param": {"__prefect_kind": "jinja", "template": "Hello {{ name }}"}}

        ctx = HydrationContext(render_jinja=False, jinja_context={"name": "world"})
        assert hydrate(values, ctx) == {"param": ValidJinja("Hello {{ name }}")}

        # render
        ctx = HydrationContext(render_jinja=True, jinja_context={"name": "world"})
        assert hydrate(values, ctx) == {"param": "Hello world"}

        # render with no jinja_context
        ctx = HydrationContext(render_jinja=True, jinja_context={})
        assert hydrate(values, ctx) == {"param": "Hello "}

    def test_jinja_type_coercion(self):
        """Test that Jinja templates automatically coerce numeric strings to appropriate types."""
        # Test integer coercion
        values = {"param": {"__prefect_kind": "jinja", "template": "{{ value }}"}}
        ctx = HydrationContext(render_jinja=True, jinja_context={"value": 42})
        result = hydrate(values, ctx)
        assert result == {"param": 42}
        assert isinstance(result["param"], int)

        # Test float coercion
        values = {"param": {"__prefect_kind": "jinja", "template": "{{ value }}"}}
        ctx = HydrationContext(render_jinja=True, jinja_context={"value": 3.14})
        result = hydrate(values, ctx)
        assert result == {"param": 3.14}
        assert isinstance(result["param"], float)

        # Test string remains string
        values = {"param": {"__prefect_kind": "jinja", "template": "Hello {{ name }}"}}
        ctx = HydrationContext(render_jinja=True, jinja_context={"name": "world"})
        result = hydrate(values, ctx)
        assert result == {"param": "Hello world"}
        assert isinstance(result["param"], str)

        # Test numeric string coercion
        values = {"param": {"__prefect_kind": "jinja", "template": "42"}}
        ctx = HydrationContext(render_jinja=True, jinja_context={})
        result = hydrate(values, ctx)
        assert result == {"param": 42}
        assert isinstance(result["param"], int)

        # Test float string coercion
        values = {"param": {"__prefect_kind": "jinja", "template": "3.14"}}
        ctx = HydrationContext(render_jinja=True, jinja_context={})
        result = hydrate(values, ctx)
        assert result == {"param": 3.14}
        assert isinstance(result["param"], float)

        # Test edge case: string that looks like float but is actually int
        values = {"param": {"__prefect_kind": "jinja", "template": "42"}}
        ctx = HydrationContext(render_jinja=True, jinja_context={})
        result = hydrate(values, ctx)
        assert result == {"param": 42}
        assert isinstance(result["param"], int)

        # Test whitespace handling
        values = {"param": {"__prefect_kind": "jinja", "template": "  42  "}}
        ctx = HydrationContext(render_jinja=True, jinja_context={})
        result = hydrate(values, ctx)
        assert result == {"param": 42}
        assert isinstance(result["param"], int)

        # Test non-numeric string stays string
        values = {"param": {"__prefect_kind": "jinja", "template": "not-a-number"}}
        ctx = HydrationContext(render_jinja=True, jinja_context={})
        result = hydrate(values, ctx)
        assert result == {"param": "not-a-number"}
        assert isinstance(result["param"], str)

        # Test negative numbers
        values = {"param": {"__prefect_kind": "jinja", "template": "-42"}}
        ctx = HydrationContext(render_jinja=True, jinja_context={})
        result = hydrate(values, ctx)
        assert result == {"param": -42}
        assert isinstance(result["param"], int)

        values = {"param": {"__prefect_kind": "jinja", "template": "-3.14"}}
        ctx = HydrationContext(render_jinja=True, jinja_context={})
        result = hydrate(values, ctx)
        assert result == {"param": -3.14}
        assert isinstance(result["param"], float)

        # Test that JSON filter templates are not coerced
        values = {"param": {"__prefect_kind": "jinja", "template": "{{ 42 | tojson }}"}}
        ctx = HydrationContext(render_jinja=True, jinja_context={})
        result = hydrate(values, ctx)
        assert result == {"param": "42"}  # String, not integer
        assert isinstance(result["param"], str)


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
            # variable not found in context and we don't render it
            # we just assume it's fine
            (
                {
                    "param": {
                        "__prefect_kind": "workspace_variable",
                        "variable_name": "my-var",
                    }
                },
                {"param": WorkspaceVariable("my-var")},
                HydrationContext(render_workspace_variables=False),
            ),
            # variable exists in context and we don't render it
            #
            (
                {
                    "param": {
                        "__prefect_kind": "workspace_variable",
                        "variable_name": "my-var",
                    }
                },
                {"param": WorkspaceVariable("my-var")},
                HydrationContext(
                    workspace_variables={"my-var": "my-value"},
                    render_workspace_variables=False,
                ),
            ),
            # variable not found in context and we render it
            (
                {
                    "param": {
                        "__prefect_kind": "workspace_variable",
                        "variable_name": "my-var",
                    }
                },
                {"param": WorkspaceVariableNotFound("my-var")},
                HydrationContext(render_workspace_variables=True),
            ),
            # variable exists in context and we render it
            (
                {
                    "param": {
                        "__prefect_kind": "workspace_variable",
                        "variable_name": "my-var",
                    }
                },
                {"param": "my-value"},
                HydrationContext(
                    workspace_variables={"my-var": "my-value"},
                    render_workspace_variables=True,
                ),
            ),
        ],
    )
    def test_hydrate_with_null_prefect_kind(self, input_object, expected_output, ctx):
        hydrated_value = hydrate(input_object, ctx)
        assert hydrated_value == expected_output


class TestNestedHydration:
    @pytest.mark.parametrize(
        "input_object, expected_output, ctx",
        [
            (
                # The workspace variable is resolved first.
                # It returns a jinja template that renders
                # and outputs a JSON string of '"4"'.
                # the JSON string is then decoded to give
                # an actual integer value.
                {
                    "param": {
                        "__prefect_kind": "json",
                        "value": {
                            "__prefect_kind": "jinja",
                            "template": {
                                "__prefect_kind": "workspace_variable",
                                "variable_name": "2_plus_2",
                            },
                        },
                    }
                },
                {"param": 4},
                HydrationContext(
                    render_jinja=True,
                    render_workspace_variables=True,
                    workspace_variables={"2_plus_2": "{{ (2 + 2) | tojson }}"},
                ),
            ),
        ],
    )
    def test_nested_hydration(self, input_object, expected_output, ctx):
        assert hydrate(input_object, ctx) == expected_output

    @pytest.mark.parametrize(
        "input_object, expected_output, ctx",
        [
            (
                {
                    "my_object": {
                        "__prefect_kind": "json",
                        "value": {
                            "__prefect_kind": "jinja",
                            "template": "{{ event.payload.body | tojson }}",
                        },
                    }
                },
                {"my_object": {"json_key": "json_value"}},
                HydrationContext(
                    jinja_context={
                        "event": {"payload": {"body": {"json_key": "json_value"}}}
                    },
                    render_jinja=True,
                ),
            ),
        ],
    )
    def test_extract_an_object(self, input_object, expected_output, ctx):
        assert hydrate(input_object, ctx) == expected_output

    @pytest.mark.parametrize(
        "input_object, expected_output, ctx",
        [
            (
                {
                    "my_object": {
                        "__prefect_kind": "json",
                        "value": {
                            "__prefect_kind": "jinja",
                            "template": "{{ event.payload.body | tojson }}",
                        },
                    }
                },
                {"my_object": ValidJinja("{{ event.payload.body | tojson }}")},
                HydrationContext(
                    jinja_context={
                        "event": {"payload": {"body": {"json_key": "json_value"}}}
                    },
                    render_jinja=False,
                ),
            ),
        ],
    )
    def test_placeholders_bubble_up(self, input_object, expected_output, ctx):
        # render_jinja=False, so the jinja template is not rendered.
        # If the parent __prefect_kind sees a Placeholder, it should just continue to bubble
        # the Placeholder up the chain.
        assert hydrate(input_object, ctx) == expected_output
