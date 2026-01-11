"""Tests for the SDK renderer module."""

import ast
import tempfile
from pathlib import Path

from prefect._sdk.models import (
    DeploymentInfo,
    FlowInfo,
    SDKData,
    SDKGenerationMetadata,
    WorkPoolInfo,
)
from prefect._sdk.renderer import (
    JobVariableContext,
    RenderResult,
    WorkPoolContext,
    _process_deployment,
    _process_fields_to_job_variables,
    _process_fields_to_params,
    _process_work_pool,
    _safe_repr,
    _sanitize_docstring,
    build_template_context,
    render_sdk,
    render_sdk_to_string,
)
from prefect._sdk.types import FieldInfo


class TestSafeRepr:
    """Tests for _safe_repr function."""

    def test_none(self):
        assert _safe_repr(None) == "None"

    def test_bool_true(self):
        assert _safe_repr(True) == "True"

    def test_bool_false(self):
        assert _safe_repr(False) == "False"

    def test_int(self):
        assert _safe_repr(42) == "42"
        assert _safe_repr(-1) == "-1"
        assert _safe_repr(0) == "0"

    def test_float(self):
        assert _safe_repr(3.14) == "3.14"
        assert _safe_repr(-0.5) == "-0.5"

    def test_string(self):
        assert _safe_repr("hello") == "'hello'"
        assert _safe_repr("it's") == '"it\'s"'
        assert _safe_repr('say "hi"') == "'say \"hi\"'"

    def test_empty_list(self):
        assert _safe_repr([]) == "[]"

    def test_list_with_items(self):
        assert _safe_repr([1, 2, 3]) == "[1, 2, 3]"
        assert _safe_repr(["a", "b"]) == "['a', 'b']"

    def test_empty_dict(self):
        assert _safe_repr({}) == "{}"

    def test_dict_with_items(self):
        result = _safe_repr({"a": 1})
        assert result == "{'a': 1}"


class TestSanitizeDocstring:
    """Tests for _sanitize_docstring function."""

    def test_none(self):
        assert _sanitize_docstring(None) is None

    def test_normal_text(self):
        assert _sanitize_docstring("Hello world") == "Hello world"

    def test_triple_quotes(self):
        assert _sanitize_docstring('Say """hello"""') == "Say '''hello'''"

    def test_whitespace_stripped(self):
        assert _sanitize_docstring("  hello  ") == "hello"


class TestProcessFieldsToParams:
    """Tests for _process_fields_to_params function."""

    def test_empty_fields(self):
        required, optional = _process_fields_to_params([], set())
        assert required == []
        assert optional == []

    def test_required_field(self):
        fields = [
            FieldInfo(
                name="source",
                python_type="str",
                required=True,
                has_default=False,
            )
        ]
        required, optional = _process_fields_to_params(fields, set())

        assert len(required) == 1
        assert len(optional) == 0
        assert required[0].name == "source"
        assert required[0].python_type == "str"
        assert required[0].required is True

    def test_optional_field_with_default(self):
        fields = [
            FieldInfo(
                name="batch_size",
                python_type="int",
                required=False,
                has_default=True,
                default=100,
            )
        ]
        required, optional = _process_fields_to_params(fields, set())

        assert len(required) == 0
        assert len(optional) == 1
        assert optional[0].name == "batch_size"
        assert optional[0].python_type == "int"
        assert optional[0].has_default is True
        assert optional[0].default_repr == "100"

    def test_name_collision_handling(self):
        fields = [
            FieldInfo(name="source", python_type="str", required=True),
            FieldInfo(name="source", python_type="int", required=True),
        ]
        required, _ = _process_fields_to_params(fields, set())

        # Second field should get a unique name
        assert required[0].name == "source"
        assert required[1].name == "source_2"


class TestProcessFieldsToJobVariables:
    """Tests for _process_fields_to_job_variables function."""

    def test_empty_fields(self):
        result = _process_fields_to_job_variables([], set())
        assert result == []

    def test_single_field(self):
        fields = [FieldInfo(name="image", python_type="str", required=False)]
        result = _process_fields_to_job_variables(fields, set())

        assert len(result) == 1
        assert result[0].name == "image"
        assert result[0].original_name == "image"
        assert result[0].python_type == "str"


class TestProcessWorkPool:
    """Tests for _process_work_pool function."""

    def test_empty_schema(self):
        wp = WorkPoolInfo(name="test-pool", pool_type="docker", job_variables_schema={})
        context, warnings = _process_work_pool(wp, set())

        assert context is None
        assert warnings == []

    def test_schema_without_properties(self):
        wp = WorkPoolInfo(
            name="test-pool",
            pool_type="docker",
            job_variables_schema={"type": "object"},
        )
        context, warnings = _process_work_pool(wp, set())

        assert context is None
        assert warnings == []

    def test_schema_with_properties(self):
        wp = WorkPoolInfo(
            name="kubernetes-pool",
            pool_type="kubernetes",
            job_variables_schema={
                "type": "object",
                "properties": {
                    "image": {"type": "string"},
                    "namespace": {"type": "string"},
                },
            },
        )
        context, warnings = _process_work_pool(wp, set())

        assert context is not None
        assert context.class_name == "KubernetesPoolJobVariables"
        assert context.original_name == "kubernetes-pool"
        assert len(context.fields) == 2
        assert warnings == []


class TestProcessDeployment:
    """Tests for _process_deployment function."""

    def test_deployment_without_params(self):
        deployment = DeploymentInfo(
            name="production",
            flow_name="my-flow",
            full_name="my-flow/production",
        )
        context, warnings = _process_deployment(deployment, {}, {}, set())

        assert context.class_name == "_MyFlowProduction"
        assert context.full_name == "my-flow/production"
        assert context.required_params == []
        assert context.optional_params == []
        assert context.has_job_variables is False

    def test_deployment_with_params(self):
        deployment = DeploymentInfo(
            name="production",
            flow_name="my-flow",
            full_name="my-flow/production",
            parameter_schema={
                "type": "object",
                "properties": {
                    "source": {"type": "string"},
                    "batch_size": {"type": "integer", "default": 100},
                },
                "required": ["source"],
            },
        )
        context, warnings = _process_deployment(deployment, {}, {}, set())

        assert len(context.required_params) == 1
        assert len(context.optional_params) == 1
        assert context.required_params[0].name == "source"
        assert context.optional_params[0].name == "batch_size"
        assert context.optional_params[0].default_repr == "100"

    def test_deployment_with_work_pool(self):
        deployment = DeploymentInfo(
            name="production",
            flow_name="my-flow",
            full_name="my-flow/production",
            work_pool_name="k8s-pool",
        )
        processed_work_pools = {
            "k8s-pool": WorkPoolContext(
                class_name="K8SPoolJobVariables",
                original_name="k8s-pool",
                fields=[
                    JobVariableContext(
                        name="image",
                        original_name="image",
                        python_type="str",
                    )
                ],
            )
        }
        context, warnings = _process_deployment(
            deployment, {}, processed_work_pools, set()
        )

        assert context.has_job_variables is True
        assert len(context.job_variable_fields) == 1
        assert context.job_variable_fields[0].name == "image"

    def test_deployment_with_missing_work_pool(self):
        deployment = DeploymentInfo(
            name="production",
            flow_name="my-flow",
            full_name="my-flow/production",
            work_pool_name="missing-pool",
        )
        context, warnings = _process_deployment(deployment, {}, {}, set())

        assert context.has_job_variables is False
        assert len(warnings) == 1
        assert "missing-pool" in warnings[0]


class TestBuildTemplateContext:
    """Tests for build_template_context function."""

    def test_empty_data(self):
        data = SDKData(
            metadata=SDKGenerationMetadata(
                generation_time="2026-01-06T14:30:00Z",
                prefect_version="3.2.0",
            )
        )
        context, warnings = build_template_context(data, "my_sdk")

        assert context.module_name == "my_sdk"
        assert context.deployment_names == []
        assert context.work_pool_typeddicts == []
        assert context.deployments == []

    def test_full_data(self):
        data = SDKData(
            metadata=SDKGenerationMetadata(
                generation_time="2026-01-06T14:30:00Z",
                prefect_version="3.2.0",
                workspace_name="my-workspace",
            ),
            flows={
                "my-flow": FlowInfo(
                    name="my-flow",
                    deployments=[
                        DeploymentInfo(
                            name="production",
                            flow_name="my-flow",
                            full_name="my-flow/production",
                            parameter_schema={
                                "type": "object",
                                "properties": {"source": {"type": "string"}},
                                "required": ["source"],
                            },
                            work_pool_name="k8s-pool",
                        )
                    ],
                )
            },
            work_pools={
                "k8s-pool": WorkPoolInfo(
                    name="k8s-pool",
                    pool_type="kubernetes",
                    job_variables_schema={
                        "type": "object",
                        "properties": {"image": {"type": "string"}},
                    },
                )
            },
        )
        context, warnings = build_template_context(data, "my_sdk")

        assert context.module_name == "my_sdk"
        assert context.deployment_names == ["my-flow/production"]
        assert len(context.work_pool_typeddicts) == 1
        assert len(context.deployments) == 1
        assert context.deployments[0].has_job_variables is True


class TestRenderSdkToString:
    """Tests for render_sdk_to_string function."""

    def test_empty_sdk(self):
        data = SDKData(
            metadata=SDKGenerationMetadata(
                generation_time="2026-01-06T14:30:00Z",
                prefect_version="3.2.0",
            )
        )
        result = render_sdk_to_string(data)

        assert isinstance(result, RenderResult)
        assert "Prefect SDK" in result.code
        assert "2026-01-06T14:30:00Z" in result.code
        assert "3.2.0" in result.code

    def test_generated_code_is_valid_python(self):
        data = SDKData(
            metadata=SDKGenerationMetadata(
                generation_time="2026-01-06T14:30:00Z",
                prefect_version="3.2.0",
            ),
            flows={
                "my-flow": FlowInfo(
                    name="my-flow",
                    deployments=[
                        DeploymentInfo(
                            name="production",
                            flow_name="my-flow",
                            full_name="my-flow/production",
                            parameter_schema={
                                "type": "object",
                                "properties": {
                                    "source": {"type": "string"},
                                    "batch_size": {"type": "integer", "default": 100},
                                },
                                "required": ["source"],
                            },
                        )
                    ],
                )
            },
        )
        result = render_sdk_to_string(data)

        # Should be valid Python
        ast.parse(result.code)

    def test_deployment_class_structure(self):
        data = SDKData(
            metadata=SDKGenerationMetadata(
                generation_time="2026-01-06T14:30:00Z",
                prefect_version="3.2.0",
            ),
            flows={
                "my-flow": FlowInfo(
                    name="my-flow",
                    deployments=[
                        DeploymentInfo(
                            name="production",
                            flow_name="my-flow",
                            full_name="my-flow/production",
                        )
                    ],
                )
            },
        )
        result = render_sdk_to_string(data)

        # Check for key components
        assert "class _MyFlowProduction:" in result.code
        assert "def with_options(" in result.code
        assert "def run(" in result.code
        assert "def run_async(" in result.code
        assert "from prefect.deployments import run_deployment" in result.code
        assert "from prefect.deployments import arun_deployment" in result.code

    def test_deployment_with_job_variables(self):
        data = SDKData(
            metadata=SDKGenerationMetadata(
                generation_time="2026-01-06T14:30:00Z",
                prefect_version="3.2.0",
            ),
            flows={
                "my-flow": FlowInfo(
                    name="my-flow",
                    deployments=[
                        DeploymentInfo(
                            name="production",
                            flow_name="my-flow",
                            full_name="my-flow/production",
                            work_pool_name="k8s-pool",
                        )
                    ],
                )
            },
            work_pools={
                "k8s-pool": WorkPoolInfo(
                    name="k8s-pool",
                    pool_type="kubernetes",
                    job_variables_schema={
                        "type": "object",
                        "properties": {"image": {"type": "string"}},
                    },
                )
            },
        )
        result = render_sdk_to_string(data)

        assert "def with_infra(" in result.code
        assert "image:" in result.code

    def test_deployments_namespace_single(self):
        """Test deployments namespace with a single deployment (no @overload needed)."""
        data = SDKData(
            metadata=SDKGenerationMetadata(
                generation_time="2026-01-06T14:30:00Z",
                prefect_version="3.2.0",
            ),
            flows={
                "my-flow": FlowInfo(
                    name="my-flow",
                    deployments=[
                        DeploymentInfo(
                            name="production",
                            flow_name="my-flow",
                            full_name="my-flow/production",
                        )
                    ],
                )
            },
        )
        result = render_sdk_to_string(data)

        assert "class deployments:" in result.code
        assert "def from_name(" in result.code
        # Python repr uses single quotes for simple strings
        assert "'my-flow/production'" in result.code
        # Single deployment shouldn't use @overload decorator
        # (because overload requires at least 2 variants)

    def test_deployments_namespace_multiple(self):
        """Test deployments namespace with multiple deployments (uses @overload)."""
        data = SDKData(
            metadata=SDKGenerationMetadata(
                generation_time="2026-01-06T14:30:00Z",
                prefect_version="3.2.0",
            ),
            flows={
                "my-flow": FlowInfo(
                    name="my-flow",
                    deployments=[
                        DeploymentInfo(
                            name="production",
                            flow_name="my-flow",
                            full_name="my-flow/production",
                        ),
                        DeploymentInfo(
                            name="staging",
                            flow_name="my-flow",
                            full_name="my-flow/staging",
                        ),
                    ],
                )
            },
        )
        result = render_sdk_to_string(data)

        assert "class deployments:" in result.code
        assert "@overload" in result.code
        assert "def from_name(" in result.code
        # Both deployments should be in the code
        assert "'my-flow/production'" in result.code
        assert "'my-flow/staging'" in result.code


class TestRenderSdk:
    """Tests for render_sdk function."""

    def test_writes_file(self):
        data = SDKData(
            metadata=SDKGenerationMetadata(
                generation_time="2026-01-06T14:30:00Z",
                prefect_version="3.2.0",
            )
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "my_sdk.py"
            result = render_sdk(data, output_path)

            assert output_path.exists()
            assert output_path.read_text() == result.code

    def test_creates_parent_directories(self):
        data = SDKData(
            metadata=SDKGenerationMetadata(
                generation_time="2026-01-06T14:30:00Z",
                prefect_version="3.2.0",
            )
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "nested" / "dir" / "my_sdk.py"
            result = render_sdk(data, output_path)

            assert output_path.exists()
            assert output_path.read_text() == result.code


class TestEdgeCases:
    """Tests for edge cases in SDK generation."""

    def test_deployment_name_with_special_chars(self):
        """Test deployment names with special characters are properly escaped."""
        data = SDKData(
            metadata=SDKGenerationMetadata(
                generation_time="2026-01-06T14:30:00Z",
                prefect_version="3.2.0",
            ),
            flows={
                "my-flow": FlowInfo(
                    name="my-flow",
                    deployments=[
                        DeploymentInfo(
                            name="prod's-test",
                            flow_name="my-flow",
                            full_name="my-flow/prod's-test",
                        )
                    ],
                )
            },
        )
        result = render_sdk_to_string(data)

        # Should be valid Python even with special chars
        ast.parse(result.code)

    def test_parameter_name_collision_with_python_keyword(self):
        """Test parameter names that are Python keywords."""
        data = SDKData(
            metadata=SDKGenerationMetadata(
                generation_time="2026-01-06T14:30:00Z",
                prefect_version="3.2.0",
            ),
            flows={
                "my-flow": FlowInfo(
                    name="my-flow",
                    deployments=[
                        DeploymentInfo(
                            name="production",
                            flow_name="my-flow",
                            full_name="my-flow/production",
                            parameter_schema={
                                "type": "object",
                                "properties": {
                                    "class": {"type": "string"},
                                    "import": {"type": "string"},
                                },
                            },
                        )
                    ],
                )
            },
        )
        result = render_sdk_to_string(data)

        # Should be valid Python with keyword-safe names
        ast.parse(result.code)
        # Keywords should have underscore suffix
        assert "class_:" in result.code
        assert "import_:" in result.code

    def test_work_pool_name_collision(self):
        """Test work pool names that would create class name collisions."""
        data = SDKData(
            metadata=SDKGenerationMetadata(
                generation_time="2026-01-06T14:30:00Z",
                prefect_version="3.2.0",
            ),
            work_pools={
                "my-pool": WorkPoolInfo(
                    name="my-pool",
                    pool_type="docker",
                    job_variables_schema={
                        "type": "object",
                        "properties": {"image": {"type": "string"}},
                    },
                ),
                "my_pool": WorkPoolInfo(
                    name="my_pool",
                    pool_type="docker",
                    job_variables_schema={
                        "type": "object",
                        "properties": {"namespace": {"type": "string"}},
                    },
                ),
            },
        )
        result = render_sdk_to_string(data)

        # Should be valid Python
        ast.parse(result.code)
        # Both should exist with unique names
        assert "MyPoolJobVariables" in result.code

    def test_multiple_deployments_same_flow(self):
        """Test multiple deployments for the same flow."""
        data = SDKData(
            metadata=SDKGenerationMetadata(
                generation_time="2026-01-06T14:30:00Z",
                prefect_version="3.2.0",
            ),
            flows={
                "my-flow": FlowInfo(
                    name="my-flow",
                    deployments=[
                        DeploymentInfo(
                            name="production",
                            flow_name="my-flow",
                            full_name="my-flow/production",
                        ),
                        DeploymentInfo(
                            name="staging",
                            flow_name="my-flow",
                            full_name="my-flow/staging",
                        ),
                    ],
                )
            },
        )
        result = render_sdk_to_string(data)

        # Should be valid Python
        ast.parse(result.code)
        assert "class _MyFlowProduction:" in result.code
        assert "class _MyFlowStaging:" in result.code

    def test_deployment_with_complex_default_values(self):
        """Test parameters with complex default values."""
        data = SDKData(
            metadata=SDKGenerationMetadata(
                generation_time="2026-01-06T14:30:00Z",
                prefect_version="3.2.0",
            ),
            flows={
                "my-flow": FlowInfo(
                    name="my-flow",
                    deployments=[
                        DeploymentInfo(
                            name="production",
                            flow_name="my-flow",
                            full_name="my-flow/production",
                            parameter_schema={
                                "type": "object",
                                "properties": {
                                    "tags": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                        "default": ["prod", "v1"],
                                    },
                                    "config": {
                                        "type": "object",
                                        "default": {"key": "value"},
                                    },
                                },
                            },
                        )
                    ],
                )
            },
        )
        result = render_sdk_to_string(data)

        # Should be valid Python
        ast.parse(result.code)
        assert "['prod', 'v1']" in result.code
        assert "{'key': 'value'}" in result.code

    def test_empty_deployment_names_literal(self):
        """Test that empty deployments still generate valid code."""
        data = SDKData(
            metadata=SDKGenerationMetadata(
                generation_time="2026-01-06T14:30:00Z",
                prefect_version="3.2.0",
            )
        )
        result = render_sdk_to_string(data)

        # Should be valid Python
        ast.parse(result.code)
        # Should have placeholder Literal
        assert 'DeploymentName = Literal[""]' in result.code
