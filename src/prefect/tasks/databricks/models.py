from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Extra, Field, validator


class TaskDependency(BaseModel):
    task_key: str


class AutoScale(BaseModel):
    min_workers: int
    max_workers: int


class AwsAvailability(Enum):
    SPOT = "SPOT"
    ON_DEMAND = "ON_DEMAND"
    SPOT_WITH_FALLBACK = "SPOT_WITH_FALLBACK"


class EbsVolumeType(Enum):
    GENERAL_PURPOSE_SSD = "GENERAL_PURPOSE_SSD"
    THROUGHPUT_OPTIMIZED_HDD = "THROUGHPUT_OPTIMIZED_HDD"


class AwsAttributes(BaseModel):
    first_on_demand: Optional[int] = None
    availability: Optional[AwsAvailability] = None
    zone_id: Optional[str] = None
    instance_profile_arn: Optional[str] = None
    spot_bid_price_percent: Optional[int] = None
    ebs_volume_type: Optional[EbsVolumeType] = None
    ebs_volume_count: Optional[int] = None
    ebs_volume_size: Optional[int] = None
    ebs_volume_iops: Optional[int] = None
    ebs_volume_throughput: Optional[int] = None


class DbfsStorageInfo(BaseModel):
    destination: Optional[str] = None


class S3StorageInfo(BaseModel):
    destination: Optional[str] = None
    region: Optional[str] = None
    endpoint: Optional[str] = None
    enable_encryption: Optional[bool] = None
    encryption_type: Optional[str] = None
    kms_key: Optional[str] = None
    canned_acl: Optional[str] = None


class FileStorageInfo(BaseModel):
    destination: Optional[str] = None


class ClusterLogConf(BaseModel):
    dbfs: Optional[DbfsStorageInfo] = None
    s3: Optional[S3StorageInfo] = None


class InitScriptInfo(BaseModel):
    dbfs: Optional[DbfsStorageInfo] = None
    file: Optional[FileStorageInfo] = None
    S3: Optional[S3StorageInfo] = None


class NewCluster(BaseModel, extra=Extra.allow):
    spark_version: str
    spark_conf: Dict = Field(default_factory=dict)
    node_type_id: Optional[str] = None
    autoscale: Optional[AutoScale] = None
    num_workers: Optional[int] = None
    aws_attributes: Optional[AwsAttributes] = None
    driver_node_type_id: Optional[str] = None
    ssh_public_keys: Optional[List[str]] = None
    custom_tags: Optional[Dict[str, Any]] = None
    cluster_log_conf: Optional[ClusterLogConf] = None
    init_scripts: Optional[List[InitScriptInfo]] = None
    spark_env_vars: Optional[Dict] = None
    enable_elastic_disk: Optional[bool] = None
    driver_instance_pool_id: Optional[str] = None
    instance_pool_id: Optional[str] = None
    policy_id: Optional[str] = None
    data_security_mode: Optional[str] = None
    single_user_name: Optional[str] = None

    @validator("instance_pool_id", always=True, pre=True)
    def node_type_or_instance_pool(cls, instance_pool_id, values):
        node_type_id = values.get("node_type_id")
        if instance_pool_id is not None and node_type_id is not None:
            raise ValueError(
                "Cannot specify instance_pool_id if node_type_id has been specified"
            )

        if instance_pool_id is None and node_type_id is None:
            raise ValueError("Must specify either instance_pool_id or node_type_id")
        return instance_pool_id


class NotebookTask(BaseModel):
    notebook_path: str
    base_parameters: Optional[Dict[str, Any]] = None


class SparkJarTask(BaseModel):
    main_class_name: str
    parameters: List[str] = Field(default_factory=list)


class SparkPythonTask(BaseModel):
    python_file: str
    parameters: List[str] = Field(default_factory=list)


class SparkSubmitTask(BaseModel):
    parameters: List[str]


class PipelineTask(BaseModel):
    pipeline_id: str


class PythonWheelTask(BaseModel):
    package_name: str
    entry_point: Optional[str] = None
    parameters: List[str] = Field(default_factory=list)


class MavenLibrary(BaseModel):
    coordinates: str
    repo: Optional[str] = None
    exclusions: List[str] = Field(default_factory=list)


class PythonPyPiLibrary(BaseModel):
    package: str
    repo: Optional[str] = None


class RCranLibrary(BaseModel):
    package: str
    repo: Optional[str] = None


class Library(BaseModel):
    jar: Optional[str] = None
    egg: Optional[str] = None
    whl: Optional[str] = None
    pypi: Optional[PythonPyPiLibrary] = None
    maven: Optional[MavenLibrary] = None
    cran: Optional[RCranLibrary] = None


class JobEmailNotifications(BaseModel):
    on_start: List[str] = Field(default_factory=list)
    on_success: List[str] = Field(default_factory=list)
    on_failure: List[str] = Field(default_factory=list)
    no_alert_for_skipped_runs: bool = False


class JobTaskSettings(BaseModel):
    task_key: str
    description: Optional[str] = None
    depends_on: List[TaskDependency] = Field(default_factory=list)
    existing_cluster_id: Optional[str] = None
    new_cluster: Optional[NewCluster] = None
    job_cluster_key: Optional[str] = None
    notebook_task: Optional[NotebookTask] = None
    spark_jar_task: Optional[SparkJarTask] = None
    spark_python_task: Optional[SparkPythonTask] = None
    spark_submit_task: Optional[SparkSubmitTask] = None
    pipeline_task: Optional[PipelineTask] = None
    python_wheel_task: Optional[PythonWheelTask] = None
    libraries: Optional[List[Library]] = None
    email_notifications: Optional[JobEmailNotifications] = None
    timeout_seconds: Optional[int] = None
    max_retries: Optional[int] = None
    min_retry_interval_millis: Optional[int] = None
    retry_on_timeout: Optional[bool] = None


class JobCluster(BaseModel):
    job_cluster_key: str
    new_cluster: Optional[NewCluster] = None


class CanManage(Enum):
    CAN_MANAGE = "CAN_MANAGE"


class CanManageRun(Enum):
    CAN_MANAGE_RUN = "CAN_MANAGE_RUN"


class CanView(Enum):
    CAN_VIEW = "CAN_VIEW"


class IsOwner(Enum):
    IS_OWNER = "IS_OWNER"


class PermissionLevel(BaseModel):
    __root__: Union[CanManage, CanManageRun, CanView, IsOwner]


class PermissionLevelForGroup(BaseModel):
    __root__: Union[CanManage, CanManageRun, CanView]


class AccessControlRequestForUser(BaseModel):
    class Config:
        use_enum_values = True

    user_name: str
    permission_level: Union[CanManage, CanManageRun, CanView, IsOwner]


class AccessControlRequestForGroup(BaseModel):
    class Config:
        use_enum_values = True

    group_name: str
    permission_level: Union[CanManage, CanManageRun, CanView]


class AccessControlRequest(BaseModel):
    __root__: Union[AccessControlRequestForUser, AccessControlRequestForGroup]


class GitSource(BaseModel, extra=Extra.allow):
    git_url: str
    git_provider: str
    git_branch: Optional[str] = None
    git_tag: Optional[str] = None
    git_commit: Optional[str] = None

    @validator("git_tag", always=True)
    def branch_or_tag(cls, v, values):
        if "git_branch" in values is not None and v:
            raise ValueError("Cannot specify git tag if git branch has been specified")
        return v

    @validator("git_branch", always=True)
    def commit_or_branch(cls, v, values):
        if "git_commit" in values is not None and v:
            raise ValueError(
                "Cannot specify git branch if git commit has been specified"
            )
        return v

    @validator("git_commit", always=True)
    def tag_or_commit(cls, v, values):
        if "git_tag" in values is not None and v:
            raise ValueError("Cannot specify git commit if git tag has been specified")
        return v
