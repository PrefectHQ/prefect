from typing import Callable

from marshmallow import fields, Schema, pre_dump, post_load, ValidationError

from prefect.utilities.serialization import JSONCompatible
from prefect.run_configs import RunConfig, KubernetesJob


class RunConfigSchema(Schema):
    cls_to_spec_schema = {}
    kind_to_cls = {}

    labels = fields.List(fields.String())
    kind = fields.String()
    spec = fields.Dict(keys=fields.String())

    @pre_dump
    def pre_dump(self, obj: RunConfig, **kwargs) -> dict:
        cls = type(obj)
        if cls in self.cls_to_spec_schema:
            schema = self.cls_to_spec_schema[cls]()
            spec = schema.dump(obj)
            return {
                "labels": getattr(obj, "labels", None),
                "kind": cls.__name__,
                "spec": spec,
            }
        raise ValidationError(f"Don't know how to serialize {cls.__name__} objects")

    @post_load
    def post_load(self, obj: dict, **kwargs) -> RunConfig:
        kind = obj.get("kind")
        if kind is None:
            raise ValidationError("No `RunConfig` kind found")
        elif kind not in self.kind_to_cls:
            raise ValidationError(f"Unknown `RunConfig` kind '{kind}'")
        cls = self.kind_to_cls[kind]
        labels = obj.get("labels")
        spec = obj.get("spec", {})
        return cls(labels=labels, **spec)


def register(run_config_cls: Callable) -> Callable:
    """Decorator to register a RunConfig schema with its corresponding class."""

    def inner(spec: Callable) -> Callable:
        RunConfigSchema.cls_to_spec_schema[run_config_cls] = spec
        RunConfigSchema.kind_to_cls[run_config_cls.__name__] = run_config_cls
        return spec

    return inner


@register(KubernetesJob)
class KubernetesJobSpecSchema(Schema):
    job_template_path = fields.String(allow_none=True)
    job_template = JSONCompatible(allow_none=True)
    image = fields.String(allow_none=True)
    env = fields.Dict(keys=fields.String(), allow_none=True)
    cpu_limit = (fields.String(allow_none=True),)
    cpu_request = fields.String(allow_none=True)
    memory_limit = (fields.String(allow_none=True),)
    memory_request = fields.String(allow_none=True)
