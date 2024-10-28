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
