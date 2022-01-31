from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional, List, Any, Union


@dataclass
class TaskDependency:
    task_key: str


@dataclass
class AutoScale:
    min_workers: int
    max_workers: int


class AwsAvailability(Enum):
    SPOT = "SPOT"
    ON_DEMAND = "ON_DEMAND"
    SPOT_WITH_FALLBACK = "SPOT_WITH_FALLBACK"


class EbsVolumeType(Enum):
    GENERAL_PURPOSE_SSD = "GENERAL_PURPOSE_SSD"
    THROUGHPUT_OPTIMIZED_HDD = "THROUGHPUT_OPTIMIZED_HDD"


@dataclass
class AwsAttributes:
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


@dataclass
class DbfsStorageInfo:
    destination: Optional[str] = None


@dataclass
class S3StorageInfo:
    destination: Optional[str] = None
    region: Optional[str] = None
    endpoint: Optional[str] = None
    enable_encryption: Optional[bool] = None
    encryption_type: Optional[str] = None
    kms_key: Optional[str] = None
    canned_acl: Optional[str] = None


@dataclass
class FileStorageInfo:
    destination: Optional[str] = None


@dataclass
class ClusterLogConf:
    dbfs: Optional[DbfsStorageInfo] = None
    s3: Optional[S3StorageInfo] = None


@dataclass
class InitScriptInfo:
    dbfs: Optional[DbfsStorageInfo] = None
    file: Optional[FileStorageInfo] = None
    S3: Optional[S3StorageInfo] = None


@dataclass
class NewCluster:
    autoscale: AutoScale
    spark_version: str
    node_type_id: str
    spark_conf: Dict = field(default_factory=dict)
    num_workers: Optional[int] = None
    aws_attributes: Optional[AwsAttributes] = None
    driver_node_type_id: Optional[str] = None
    ssh_public_keys: Optional[List[str]] = None
    custom_tags: Optional[str] = None
    cluster_log_conf: Optional[ClusterLogConf] = None
    init_scripts: Optional[List[InitScriptInfo]] = None
    spark_env_vars: Optional[Dict] = None
    enable_elastic_disk: Optional[bool] = None
    driver_instance_pool_id: Optional[str] = None
    instance_pool_id: Optional[str] = None


@dataclass
class NotebookTask:
    notebook_path: str
    base_parameters: Optional[Dict[str, Any]] = None


@dataclass
class SparkJarTask:
    main_class_name: str
    parameters: List[str] = field(default_factory=list)


@dataclass
class SparkPythonTask:
    python_file: str
    parameters: List[str] = field(default_factory=list)


@dataclass
class SparkSubmitTask:
    parameters: List[str]


@dataclass
class PipelineTask:
    pipeline_id: str


@dataclass
class PythonWheelTask:
    package_name: str
    entry_point: Optional[str] = None
    parameters: List[str] = field(default_factory=list)


@dataclass
class MavenLibrary:
    coordinates: str
    repo: Optional[str] = None
    exclusions: List[str] = field(default_factory=list)


@dataclass
class PythonPyPiLibrary:
    package: str
    repo: Optional[str] = None


@dataclass
class RCranLibrary:
    package: str
    repo: Optional[str] = None


@dataclass
class Library:
    jar: Optional[str] = None
    egg: Optional[str] = None
    whl: Optional[str] = None
    pypi: Optional[PythonPyPiLibrary] = None
    maven: Optional[MavenLibrary] = None
    cran: Optional[RCranLibrary] = None


@dataclass
class JobEmailNotifications:
    on_start: List[str] = field(default_factory=list)
    on_success: List[str] = field(default_factory=list)
    on_failure: List[str] = field(default_factory=list)
    no_alert_for_skipped_runs: bool = False


@dataclass
class JobTaskSettings:
    task_key: str
    description: Optional[str] = None
    depends_on: List[TaskDependency] = field(default_factory=list)
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


@dataclass
class JobCluster:
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


@dataclass
class AccessControlRequestForUser:
    user_name: str
    permission_level: Union[CanManage, CanManageRun, CanView, IsOwner]


@dataclass
class AccessControlRequestForGroup:
    group_name: str
    permission_level: Union[CanManage, CanManageRun, CanView]
