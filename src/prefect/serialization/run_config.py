from marshmallow import fields

from prefect.utilities.serialization import JSONCompatible, OneOfSchema, ObjectSchema
from prefect.run_configs import KubernetesRun


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


class RunConfigSchema(OneOfSchema):
    type_schemas = {
        "KubernetesRun": KubernetesRunSchema,
    }
