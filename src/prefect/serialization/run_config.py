from marshmallow import fields

from prefect.utilities.serialization import JSONCompatible, OneOfSchema, ObjectSchema
from prefect.run_configs import KubernetesRun, LocalRun, DockerRun, ECSRun


class RunConfigSchemaBase(ObjectSchema):
    labels = fields.List(fields.String())


class KubernetesRunSchema(RunConfigSchemaBase):
    class Meta:
        object_class = KubernetesRun

    job_template_path = fields.String(allow_none=True)
    job_template = JSONCompatible(allow_none=True)
    image = fields.String(allow_none=True)
    env = fields.Dict(keys=fields.String(), allow_none=True)
    cpu_limit = fields.String(allow_none=True)
    cpu_request = fields.String(allow_none=True)
    memory_limit = fields.String(allow_none=True)
    memory_request = fields.String(allow_none=True)


class ECSRunSchema(RunConfigSchemaBase):
    class Meta:
        object_class = ECSRun

    task_definition_path = fields.String(allow_none=True)
    task_definition = JSONCompatible(allow_none=True)
    image = fields.String(allow_none=True)
    env = fields.Dict(keys=fields.String(), allow_none=True)
    cpu = fields.String(allow_none=True)
    memory = fields.String(allow_none=True)
    task_role_arn = fields.String(allow_none=True)
    run_task_kwargs = JSONCompatible(allow_none=True)


class LocalRunSchema(RunConfigSchemaBase):
    class Meta:
        object_class = LocalRun

    env = fields.Dict(keys=fields.String(), allow_none=True)
    working_dir = fields.String(allow_none=True)


class DockerRunSchema(RunConfigSchemaBase):
    class Meta:
        object_class = DockerRun

    image = fields.String(allow_none=True)
    env = fields.Dict(keys=fields.String(), allow_none=True)


class RunConfigSchema(OneOfSchema):
    type_schemas = {
        "KubernetesRun": KubernetesRunSchema,
        "ECSRun": ECSRunSchema,
        "LocalRun": LocalRunSchema,
        "DockerRun": DockerRunSchema,
    }
