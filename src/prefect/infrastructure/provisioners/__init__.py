from .cloud_run import CloudRunPushProvisioner

_provisioners = {
    "cloud-run:push": CloudRunPushProvisioner,
}


def get_infrastructure_provisioner_for_work_pool_type(work_pool_type: str):
    provisioner = _provisioners.get(work_pool_type)
    if provisioner is None:
        raise ValueError(f"Unsupported work pool type: {work_pool_type}")
    return provisioner()
