from marshmallow import fields

from prefect.run_configs import (
    DockerRun,
    ECSRun,
    KubernetesRun,
    LocalRun,
    UniversalRun,
    VertexRun,
)
from prefect.utilities.serialization import (
    JSONCompatible,
    ObjectSchema,
    OneOfSchema,
    SortedList,
)


class RunConfigSchemaBase(ObjectSchema):
    env = fields.Dict(keys=fields.String(), allow_none=True)
    labels = SortedList(fields.String())


class UniversalRunSchema(RunConfigSchemaBase):
    class Meta:
        object_class = UniversalRun


class KubernetesRunSchema(RunConfigSchemaBase):
    class Meta:
        object_class = KubernetesRun

    job_template_path = fields.String(allow_none=True)
    job_template = JSONCompatible(allow_none=True)
    image = fields.String(allow_none=True)
    cpu_limit = fields.String(allow_none=True)
    cpu_request = fields.String(allow_none=True)
    memory_limit = fields.String(allow_none=True)
    memory_request = fields.String(allow_none=True)
    service_account_name = fields.String(allow_none=True)
    image_pull_secrets = fields.List(fields.String(), allow_none=True)
    image_pull_policy = fields.String(allow_none=True)


class ECSRunSchema(RunConfigSchemaBase):
    class Meta:
        object_class = ECSRun

    task_definition_path = fields.String(allow_none=True)
    task_definition = JSONCompatible(allow_none=True)
    task_definition_arn = fields.String(allow_none=True)
    image = fields.String(allow_none=True)
    cpu = fields.String(allow_none=True)
    memory = fields.String(allow_none=True)
    task_role_arn = fields.String(allow_none=True)
    execution_role_arn = fields.String(allow_none=True)
    run_task_kwargs = JSONCompatible(allow_none=True)


class LocalRunSchema(RunConfigSchemaBase):
    class Meta:
        object_class = LocalRun

    working_dir = fields.String(allow_none=True)


class DockerRunSchema(RunConfigSchemaBase):
    class Meta:
        object_class = DockerRun

    ports = fields.List(fields.Int, allow_none=True)
    image = fields.String(allow_none=True)
    host_config = fields.Dict(keys=fields.String(), allow_none=True)


class VertexRunSchema(RunConfigSchemaBase):
    class Meta:
        object_class = VertexRun

    image = fields.String(allow_none=True)
    machine_type = fields.String(allow_none=True)
    scheduling = fields.Dict(keys=fields.String(), allow_none=True)
    service_account = fields.String(allow_none=True)
    network = fields.String(allow_none=True)
    worker_pool_specs = fields.List(
        fields.Dict(keys=fields.String(), allow_none=True), allow_none=True
    )


class RunConfigSchema(OneOfSchema):
    type_schemas = {
        "KubernetesRun": KubernetesRunSchema,
        "ECSRun": ECSRunSchema,
        "LocalRun": LocalRunSchema,
        "DockerRun": DockerRunSchema,
        "UniversalRun": UniversalRunSchema,
        "VertexRun": VertexRunSchema,
    }
