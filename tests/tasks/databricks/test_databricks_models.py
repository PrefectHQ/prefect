import json

import pydantic
import pytest
from pydantic import Json

from prefect.tasks.databricks.models import GitSource, NewCluster


def prefect_git_source(**kwargs):
    return GitSource(
        git_url="https://github.com/PrefectHQ/prefect/", git_provider="GitHub", **kwargs
    )


def assert_git_source_conflicting_args(**kwargs):
    with pytest.raises(pydantic.ValidationError):
        prefect_git_source(**kwargs)


def test_gitsource_branch_or_tag_are_exclusive():
    assert_git_source_conflicting_args(git_branch="main", git_tag="v1.0")


def test_gitsource_branch_or_commit_are_exclusive():
    assert_git_source_conflicting_args(git_branch="main", git_commit="78ffc7055")


def test_gitsource_commit_or_tag_are_exclusive():
    assert_git_source_conflicting_args(git_tag="v1.0", git_commit="78ffc7055")


def test_newcluster_support_tags():
    new_cluster = NewCluster(
        spark_version="10.5.x-scala2.12",
        node_type_id="i3.xlarge",
        num_workers=0,
        spark_conf={
            "spark.databricks.cluster.profile": "singleNode",
            "spark.master": "local[*]",
        },
        custom_tags='{"my-tag": 1}',
    )
    assert new_cluster.dict() == json.loads(new_cluster_json)


new_cluster_json = """
    {   "spark_version": "10.5.x-scala2.12", 
        "node_type_id": "i3.xlarge", 
        "spark_conf": 
        {
            "spark.databricks.cluster.profile": "singleNode", 
            "spark.master": "local[*]"
        }, 
        "autoscale": null, 
        "num_workers": 0, 
        "aws_attributes": null, 
        "driver_node_type_id": null, 
        "ssh_public_keys": null, 
        "custom_tags": {"my-tag": 1}, 
        "cluster_log_conf": null, 
        "init_scripts": null, 
        "spark_env_vars": null, 
        "enable_elastic_disk": null, 
        "driver_instance_pool_id": null, 
        "instance_pool_id": null, 
        "policy_id": null, 
        "data_security_mode": null, 
        "single_user_name": null
    }
"""
