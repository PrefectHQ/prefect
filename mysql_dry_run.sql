CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 3d1b2a5f0f1a

CREATE TABLE artifact (
    `key` VARCHAR(255), 
    task_run_id CHAR(36), 
    flow_run_id CHAR(36), 
    type VARCHAR(255), 
    data JSON, 
    description VARCHAR(255), 
    metadata_ JSON, 
    id CHAR(36) NOT NULL DEFAULT (UUID()), 
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    CONSTRAINT pk_artifact PRIMARY KEY (id)
);

CREATE INDEX ix_artifact_updated ON artifact (updated);

CREATE INDEX ix_artifact__key_created_desc ON artifact (`key`, created DESC);

CREATE INDEX ix_artifact_task_run_id ON artifact (task_run_id);

CREATE INDEX ix_artifact__key ON artifact (`key`);

CREATE INDEX ix_artifact_key ON artifact (`key`);

CREATE INDEX ix_artifact_flow_run_id ON artifact (flow_run_id);

CREATE TABLE artifact_collection (
    `key` VARCHAR(255) NOT NULL, 
    latest_id CHAR(36) NOT NULL, 
    task_run_id CHAR(36), 
    flow_run_id CHAR(36), 
    type VARCHAR(255), 
    data JSON, 
    description VARCHAR(255), 
    metadata_ JSON, 
    id CHAR(36) NOT NULL DEFAULT (UUID()), 
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    CONSTRAINT pk_artifact_collection PRIMARY KEY (id), 
    CONSTRAINT uq_artifact_collection__key UNIQUE (`key`)
);

CREATE INDEX ix_artifact_collection__key_latest_id ON artifact_collection (`key`, latest_id);

CREATE INDEX ix_artifact_collection_updated ON artifact_collection (updated);

CREATE TABLE automation (
    name VARCHAR(255) NOT NULL, 
    description VARCHAR(255) NOT NULL, 
    enabled BOOL NOT NULL DEFAULT '1', 
    tags JSON NOT NULL, 
    `trigger` JSON NOT NULL, 
    actions JSON NOT NULL, 
    actions_on_trigger JSON NOT NULL, 
    actions_on_resolve JSON NOT NULL, 
    id CHAR(36) NOT NULL DEFAULT (UUID()), 
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    CONSTRAINT pk_automation PRIMARY KEY (id)
);

CREATE INDEX ix_automation_updated ON automation (updated);

CREATE TABLE automation_event_follower (
    scope VARCHAR(255) NOT NULL, 
    leader_event_id CHAR(36) NOT NULL, 
    follower_event_id CHAR(36) NOT NULL, 
    received TIMESTAMP NOT NULL, 
    follower JSON NOT NULL, 
    id CHAR(36) NOT NULL DEFAULT (UUID()), 
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    CONSTRAINT pk_automation_event_follower PRIMARY KEY (id)
);

CREATE INDEX ix_ae_follower_scope_leader ON automation_event_follower (scope, leader_event_id);

CREATE INDEX ix_automation_event_follower_leader_event_id ON automation_event_follower (leader_event_id);

CREATE INDEX ix_automation_event_follower_updated ON automation_event_follower (updated);

CREATE UNIQUE INDEX uq_follower_for_scope ON automation_event_follower (scope, follower_event_id);

CREATE INDEX ix_automation_event_follower_received ON automation_event_follower (received);

CREATE INDEX ix_automation_event_follower_scope ON automation_event_follower (scope);

CREATE TABLE block_type (
    name VARCHAR(255) NOT NULL, 
    slug VARCHAR(255) NOT NULL, 
    logo_url VARCHAR(255), 
    documentation_url VARCHAR(255), 
    description VARCHAR(255), 
    code_example VARCHAR(255), 
    is_protected BOOL NOT NULL DEFAULT '0', 
    id CHAR(36) NOT NULL DEFAULT (UUID()), 
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    CONSTRAINT pk_block_type PRIMARY KEY (id)
);

CREATE UNIQUE INDEX uq_block_type__slug ON block_type (slug);

CREATE INDEX ix_block_type_updated ON block_type (updated);

CREATE INDEX trgm_ix_block_type_name ON block_type (name);

CREATE TABLE concurrency_limit (
    tag VARCHAR(255) NOT NULL, 
    concurrency_limit INTEGER NOT NULL, 
    active_slots JSON NOT NULL, 
    id CHAR(36) NOT NULL DEFAULT (UUID()), 
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    CONSTRAINT pk_concurrency_limit PRIMARY KEY (id)
);

CREATE INDEX ix_concurrency_limit_updated ON concurrency_limit (updated);

CREATE UNIQUE INDEX uq_concurrency_limit__tag ON concurrency_limit (tag);

CREATE TABLE concurrency_limit_v2 (
    active BOOL NOT NULL, 
    name VARCHAR(255) NOT NULL, 
    `limit` INTEGER NOT NULL, 
    active_slots INTEGER NOT NULL, 
    denied_slots INTEGER NOT NULL, 
    slot_decay_per_second FLOAT NOT NULL, 
    avg_slot_occupancy_seconds FLOAT NOT NULL, 
    id CHAR(36) NOT NULL DEFAULT (UUID()), 
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    CONSTRAINT pk_concurrency_limit_v2 PRIMARY KEY (id), 
    CONSTRAINT uq_concurrency_limit_v2__name UNIQUE (name)
);

CREATE INDEX ix_concurrency_limit_v2_updated ON concurrency_limit_v2 (updated);

CREATE TABLE configuration (
    `key` VARCHAR(255) NOT NULL, 
    value JSON NOT NULL, 
    id CHAR(36) NOT NULL DEFAULT (UUID()), 
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    CONSTRAINT pk_configuration PRIMARY KEY (id), 
    CONSTRAINT uq_configuration__key UNIQUE (`key`)
);

CREATE INDEX ix_configuration_key ON configuration (`key`);

CREATE INDEX ix_configuration_updated ON configuration (updated);

CREATE TABLE csrf_token (
    token VARCHAR(255) NOT NULL, 
    client VARCHAR(255) NOT NULL, 
    expiration TIMESTAMP NOT NULL, 
    id CHAR(36) NOT NULL DEFAULT (UUID()), 
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    CONSTRAINT pk_csrf_token PRIMARY KEY (id), 
    UNIQUE (client)
);

CREATE INDEX ix_csrf_token_updated ON csrf_token (updated);

CREATE TABLE event_resources (
    occurred TIMESTAMP NOT NULL, 
    resource_id VARCHAR(255) NOT NULL, 
    resource_role TEXT NOT NULL, 
    resource JSON NOT NULL, 
    event_id CHAR(36) NOT NULL, 
    id CHAR(36) NOT NULL DEFAULT (UUID()), 
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    CONSTRAINT pk_event_resources PRIMARY KEY (id)
);

CREATE INDEX ix_event_resources_updated ON event_resources (updated);

CREATE TABLE events (
    occurred TIMESTAMP NOT NULL, 
    event VARCHAR(255) NOT NULL, 
    resource_id VARCHAR(255) NOT NULL, 
    resource JSON NOT NULL, 
    related_resource_ids JSON NOT NULL, 
    related JSON NOT NULL, 
    payload JSON NOT NULL, 
    received TIMESTAMP NOT NULL, 
    recorded TIMESTAMP NOT NULL, 
    follows CHAR(36), 
    id CHAR(36) NOT NULL DEFAULT (UUID()), 
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    CONSTRAINT pk_events PRIMARY KEY (id)
);

CREATE INDEX ix_events_updated ON events (updated);

CREATE INDEX ix_events__occurred ON events (occurred);

CREATE INDEX ix_events__occurred_id ON events (occurred, id);

CREATE TABLE flow (
    name VARCHAR(255) NOT NULL, 
    tags JSON NOT NULL, 
    labels JSON, 
    id CHAR(36) NOT NULL DEFAULT (UUID()), 
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    CONSTRAINT pk_flow PRIMARY KEY (id), 
    CONSTRAINT uq_flow__name UNIQUE (name)
);

CREATE INDEX trgm_ix_flow_name ON flow (name);

CREATE INDEX ix_flow__created ON flow (created);

CREATE INDEX ix_flow_updated ON flow (updated);

CREATE TABLE log (
    name VARCHAR(255) NOT NULL, 
    level SMALLINT NOT NULL, 
    flow_run_id CHAR(36), 
    task_run_id CHAR(36), 
    message TEXT NOT NULL, 
    timestamp TIMESTAMP NOT NULL, 
    id CHAR(36) NOT NULL DEFAULT (UUID()), 
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    CONSTRAINT pk_log PRIMARY KEY (id)
);

CREATE INDEX ix_log_updated ON log (updated);

CREATE INDEX ix_log_task_run_id ON log (task_run_id);

CREATE INDEX ix_log_level ON log (level);

CREATE INDEX ix_log_timestamp ON log (timestamp);

CREATE INDEX ix_log__flow_run_id_timestamp ON log (flow_run_id, timestamp);

CREATE INDEX ix_log_flow_run_id ON log (flow_run_id);

CREATE TABLE saved_search (
    name VARCHAR(255) NOT NULL, 
    filters JSON NOT NULL, 
    id CHAR(36) NOT NULL DEFAULT (UUID()), 
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    CONSTRAINT pk_saved_search PRIMARY KEY (id), 
    CONSTRAINT uq_saved_search__name UNIQUE (name)
);

CREATE INDEX ix_saved_search_updated ON saved_search (updated);

CREATE TABLE task_run_state_cache (
    cache_key VARCHAR(255) NOT NULL, 
    cache_expiration TIMESTAMP NULL, 
    task_run_state_id CHAR(36) NOT NULL, 
    id CHAR(36) NOT NULL DEFAULT (UUID()), 
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    CONSTRAINT pk_task_run_state_cache PRIMARY KEY (id)
);

CREATE INDEX ix_task_run_state_cache_updated ON task_run_state_cache (updated);

CREATE INDEX ix_task_run_state_cache__cache_key_created_desc ON task_run_state_cache (cache_key, created DESC);

CREATE TABLE variable (
    name VARCHAR(255) NOT NULL, 
    value JSON, 
    tags JSON NOT NULL, 
    id CHAR(36) NOT NULL DEFAULT (UUID()), 
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    CONSTRAINT pk_variable PRIMARY KEY (id), 
    CONSTRAINT uq_variable__name UNIQUE (name)
);

CREATE INDEX ix_variable_updated ON variable (updated);

CREATE TABLE work_pool (
    name VARCHAR(255) NOT NULL, 
    description VARCHAR(255), 
    type VARCHAR(255) NOT NULL, 
    base_job_template JSON NOT NULL, 
    is_paused BOOL NOT NULL DEFAULT '0', 
    default_queue_id CHAR(36), 
    concurrency_limit INTEGER, 
    status ENUM('READY','NOT_READY','PAUSED') NOT NULL DEFAULT 'NOT_READY', 
    last_transitioned_status_at TIMESTAMP NULL, 
    last_status_event_id CHAR(36), 
    storage_configuration JSON NOT NULL, 
    id CHAR(36) NOT NULL DEFAULT (UUID()), 
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    CONSTRAINT pk_work_pool PRIMARY KEY (id), 
    CONSTRAINT uq_work_pool__name UNIQUE (name)
);

CREATE INDEX ix_work_pool_type ON work_pool (type);

CREATE INDEX ix_work_pool_updated ON work_pool (updated);

CREATE TABLE automation_bucket (
    automation_id CHAR(36) NOT NULL, 
    trigger_id CHAR(36) NOT NULL, 
    bucketing_key JSON NOT NULL, 
    last_event JSON, 
    start TIMESTAMP NOT NULL, 
    end TIMESTAMP NOT NULL, 
    count INTEGER NOT NULL, 
    last_operation VARCHAR(255), 
    triggered_at TIMESTAMP NULL, 
    id CHAR(36) NOT NULL DEFAULT (UUID()), 
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    CONSTRAINT pk_automation_bucket PRIMARY KEY (id), 
    CONSTRAINT fk_automation_bucket__automation_id__automation FOREIGN KEY(automation_id) REFERENCES automation (id) ON DELETE CASCADE
);

CREATE INDEX ix_automation_bucket__automation_id__end ON automation_bucket (automation_id, end);

CREATE INDEX ix_automation_bucket_updated ON automation_bucket (updated);

CREATE TABLE automation_related_resource (
    automation_id CHAR(36) NOT NULL, 
    resource_id VARCHAR(255), 
    automation_owned_by_resource BOOL NOT NULL DEFAULT '0', 
    id CHAR(36) NOT NULL DEFAULT (UUID()), 
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    CONSTRAINT pk_automation_related_resource PRIMARY KEY (id), 
    CONSTRAINT fk_automation_related_resource__automation_id__automation FOREIGN KEY(automation_id) REFERENCES automation (id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX uq_automation_related_resource__automation_id__resource_id ON automation_related_resource (automation_id, resource_id);

CREATE INDEX ix_automation_related_resource_resource_id ON automation_related_resource (resource_id);

CREATE INDEX ix_automation_related_resource_updated ON automation_related_resource (updated);

CREATE TABLE block_schema (
    checksum VARCHAR(255) NOT NULL, 
    fields JSON NOT NULL, 
    capabilities JSON NOT NULL, 
    version VARCHAR(255) NOT NULL DEFAULT 'non-versioned', 
    block_type_id CHAR(36) NOT NULL, 
    id CHAR(36) NOT NULL DEFAULT (UUID()), 
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    CONSTRAINT pk_block_schema PRIMARY KEY (id), 
    CONSTRAINT fk_block_schema__block_type_id__block_type FOREIGN KEY(block_type_id) REFERENCES block_type (id) ON DELETE cascade
);

CREATE INDEX ix_block_schema_block_type_id ON block_schema (block_type_id);

CREATE UNIQUE INDEX uq_block_schema__checksum_version ON block_schema (checksum, version);

CREATE INDEX ix_block_schema__created ON block_schema (created);

CREATE INDEX ix_block_schema_updated ON block_schema (updated);

CREATE TABLE composite_trigger_child_firing (
    automation_id CHAR(36) NOT NULL, 
    parent_trigger_id CHAR(36) NOT NULL, 
    child_trigger_id CHAR(36) NOT NULL, 
    child_firing_id CHAR(36) NOT NULL, 
    child_fired_at TIMESTAMP NULL, 
    child_firing JSON NOT NULL, 
    id CHAR(36) NOT NULL DEFAULT (UUID()), 
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    CONSTRAINT pk_composite_trigger_child_firing PRIMARY KEY (id), 
    CONSTRAINT fk_composite_trigger_child_firing__automation_id__automation FOREIGN KEY(automation_id) REFERENCES automation (id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX uq_composite_trigger_child_firing__a_id__pt_id__ct__id ON composite_trigger_child_firing (automation_id, parent_trigger_id, child_trigger_id);

CREATE INDEX ix_composite_trigger_child_firing_updated ON composite_trigger_child_firing (updated);

CREATE TABLE work_queue (
    name VARCHAR(255) NOT NULL, 
    filter JSON, 
    description VARCHAR(255) NOT NULL DEFAULT '', 
    is_paused BOOL NOT NULL DEFAULT '0', 
    concurrency_limit INTEGER, 
    priority INTEGER NOT NULL, 
    last_polled TIMESTAMP NULL, 
    status ENUM('READY','NOT_READY','PAUSED') NOT NULL DEFAULT 'NOT_READY', 
    work_pool_id CHAR(36) NOT NULL, 
    id CHAR(36) NOT NULL DEFAULT (UUID()), 
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    CONSTRAINT pk_work_queue PRIMARY KEY (id), 
    CONSTRAINT uq_work_queue__work_pool_id_name UNIQUE (work_pool_id, name), 
    CONSTRAINT fk_work_queue__work_pool_id__work_pool FOREIGN KEY(work_pool_id) REFERENCES work_pool (id) ON DELETE cascade
);

CREATE INDEX trgm_ix_work_queue_name ON work_queue (name);

CREATE INDEX ix_work_queue_work_pool_id ON work_queue (work_pool_id);

CREATE INDEX ix_work_queue_updated ON work_queue (updated);

CREATE INDEX ix_work_queue__work_pool_id_priority ON work_queue (work_pool_id, priority);

CREATE TABLE worker (
    work_pool_id CHAR(36) NOT NULL, 
    name VARCHAR(255) NOT NULL, 
    last_heartbeat_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    heartbeat_interval_seconds INTEGER, 
    status ENUM('ONLINE','OFFLINE') NOT NULL DEFAULT 'OFFLINE', 
    id CHAR(36) NOT NULL DEFAULT (UUID()), 
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    CONSTRAINT pk_worker PRIMARY KEY (id), 
    CONSTRAINT fk_worker__work_pool_id__work_pool FOREIGN KEY(work_pool_id) REFERENCES work_pool (id) ON DELETE cascade, 
    CONSTRAINT uq_worker__work_pool_id_name UNIQUE (work_pool_id, name)
);

CREATE INDEX ix_worker__work_pool_id_last_heartbeat_time ON worker (work_pool_id, last_heartbeat_time);

CREATE INDEX ix_worker_updated ON worker (updated);

CREATE INDEX ix_worker_work_pool_id ON worker (work_pool_id);

CREATE TABLE agent (
    name VARCHAR(255) NOT NULL, 
    work_queue_id CHAR(36) NOT NULL, 
    last_activity_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    id CHAR(36) NOT NULL DEFAULT (UUID()), 
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    CONSTRAINT pk_agent PRIMARY KEY (id), 
    CONSTRAINT fk_agent__work_queue_id__work_queue FOREIGN KEY(work_queue_id) REFERENCES work_queue (id), 
    CONSTRAINT uq_agent__name UNIQUE (name)
);

CREATE INDEX ix_agent_work_queue_id ON agent (work_queue_id);

CREATE INDEX ix_agent_updated ON agent (updated);

CREATE TABLE block_document (
    name VARCHAR(255) NOT NULL, 
    data JSON NOT NULL, 
    is_anonymous BOOL NOT NULL DEFAULT '0', 
    block_type_name VARCHAR(255), 
    block_type_id CHAR(36) NOT NULL, 
    block_schema_id CHAR(36) NOT NULL, 
    id CHAR(36) NOT NULL DEFAULT (UUID()), 
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    CONSTRAINT pk_block_document PRIMARY KEY (id), 
    CONSTRAINT fk_block_document__block_schema_id__block_schema FOREIGN KEY(block_schema_id) REFERENCES block_schema (id) ON DELETE cascade, 
    CONSTRAINT fk_block_document__block_type_id__block_type FOREIGN KEY(block_type_id) REFERENCES block_type (id) ON DELETE cascade
);

CREATE INDEX ix_block_document__block_type_name__name ON block_document (block_type_name, name);

CREATE INDEX ix_block_document_is_anonymous ON block_document (is_anonymous);

CREATE UNIQUE INDEX uq_block__type_id_name ON block_document (block_type_id, name);

CREATE INDEX trgm_ix_block_document_name ON block_document (name);

CREATE INDEX ix_block_document_name ON block_document (name);

CREATE INDEX ix_block_document_updated ON block_document (updated);

CREATE TABLE block_schema_reference (
    name VARCHAR(255) NOT NULL, 
    parent_block_schema_id CHAR(36) NOT NULL, 
    reference_block_schema_id CHAR(36) NOT NULL, 
    id CHAR(36) NOT NULL DEFAULT (UUID()), 
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    CONSTRAINT pk_block_schema_reference PRIMARY KEY (id), 
    CONSTRAINT fk_block_schema_reference__reference_block_schema_id__bl_6e5d FOREIGN KEY(reference_block_schema_id) REFERENCES block_schema (id) ON DELETE cascade, 
    CONSTRAINT fk_block_schema_reference__parent_block_schema_id__block_schema FOREIGN KEY(parent_block_schema_id) REFERENCES block_schema (id) ON DELETE cascade
);

CREATE INDEX ix_block_schema_reference_updated ON block_schema_reference (updated);

CREATE TABLE block_document_reference (
    name VARCHAR(255) NOT NULL, 
    parent_block_document_id CHAR(36) NOT NULL, 
    reference_block_document_id CHAR(36) NOT NULL, 
    id CHAR(36) NOT NULL DEFAULT (UUID()), 
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    CONSTRAINT pk_block_document_reference PRIMARY KEY (id), 
    CONSTRAINT fk_block_document_reference__reference_block_document_id_5759 FOREIGN KEY(reference_block_document_id) REFERENCES block_document (id) ON DELETE cascade, 
    CONSTRAINT fk_block_document_reference__parent_block_document_id__b_328f FOREIGN KEY(parent_block_document_id) REFERENCES block_document (id) ON DELETE cascade, 
    CONSTRAINT ck_block_document_reference__ck_block_document_reference_824f CHECK (parent_block_document_id != reference_block_document_id)
);

CREATE INDEX ix_block_document_reference_updated ON block_document_reference (updated);

CREATE TABLE deployment (
    name VARCHAR(255) NOT NULL, 
    version VARCHAR(255), 
    description TEXT, 
    work_queue_name VARCHAR(255), 
    infra_overrides JSON NOT NULL, 
    path VARCHAR(255), 
    entrypoint VARCHAR(255), 
    last_polled TIMESTAMP NULL, 
    status ENUM('READY','NOT_READY') NOT NULL DEFAULT 'NOT_READY', 
    flow_id CHAR(36) NOT NULL, 
    work_queue_id CHAR(36), 
    paused BOOL NOT NULL DEFAULT '0', 
    concurrency_limit INTEGER, 
    concurrency_limit_id CHAR(36), 
    concurrency_options JSON, 
    tags JSON NOT NULL, 
    labels JSON, 
    parameters JSON NOT NULL, 
    pull_steps JSON, 
    parameter_openapi_schema JSON, 
    enforce_parameter_schema BOOL NOT NULL DEFAULT '0', 
    created_by JSON, 
    updated_by JSON, 
    infrastructure_document_id CHAR(36), 
    storage_document_id CHAR(36), 
    id CHAR(36) NOT NULL DEFAULT (UUID()), 
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    CONSTRAINT pk_deployment PRIMARY KEY (id), 
    CONSTRAINT fk_deployment__storage_document_id__block_document FOREIGN KEY(storage_document_id) REFERENCES block_document (id) ON DELETE CASCADE, 
    CONSTRAINT fk_deployment__concurrency_limit_id__concurrency_limit_v2 FOREIGN KEY(concurrency_limit_id) REFERENCES concurrency_limit_v2 (id) ON DELETE SET NULL, 
    CONSTRAINT fk_deployment__work_queue_id__work_queue FOREIGN KEY(work_queue_id) REFERENCES work_queue (id) ON DELETE SET NULL, 
    CONSTRAINT fk_deployment__flow_id__flow FOREIGN KEY(flow_id) REFERENCES flow (id) ON DELETE CASCADE, 
    CONSTRAINT fk_deployment__infrastructure_document_id__block_document FOREIGN KEY(infrastructure_document_id) REFERENCES block_document (id) ON DELETE CASCADE
);

CREATE INDEX ix_deployment_flow_id ON deployment (flow_id);

CREATE INDEX ix_deployment_work_queue_id ON deployment (work_queue_id);

CREATE INDEX ix_deployment__created ON deployment (created);

CREATE INDEX ix_deployment_work_queue_name ON deployment (work_queue_name);

CREATE INDEX trgm_ix_deployment_name ON deployment (name);

CREATE INDEX ix_deployment_updated ON deployment (updated);

CREATE UNIQUE INDEX uq_deployment__flow_id_name ON deployment (flow_id, name);

CREATE INDEX ix_deployment_paused ON deployment (paused);

CREATE TABLE flow_run (
    flow_id CHAR(36) NOT NULL, 
    deployment_id CHAR(36), 
    work_queue_name VARCHAR(255), 
    flow_version VARCHAR(255), 
    deployment_version VARCHAR(255), 
    parameters JSON NOT NULL, 
    idempotency_key VARCHAR(255), 
    context JSON NOT NULL, 
    empirical_policy JSON NOT NULL, 
    tags JSON NOT NULL, 
    labels JSON, 
    created_by JSON, 
    infrastructure_pid VARCHAR(255), 
    job_variables JSON, 
    infrastructure_document_id CHAR(36), 
    parent_task_run_id CHAR(36), 
    auto_scheduled BOOL NOT NULL DEFAULT '0', 
    state_id CHAR(36), 
    work_queue_id CHAR(36), 
    name VARCHAR(255) NOT NULL, 
    state_type ENUM('SCHEDULED','PENDING','RUNNING','COMPLETED','FAILED','CANCELLED','CRASHED','PAUSED','CANCELLING'), 
    state_name VARCHAR(255), 
    state_timestamp TIMESTAMP NULL, 
    run_count INTEGER NOT NULL DEFAULT '0', 
    expected_start_time TIMESTAMP NULL, 
    next_scheduled_start_time TIMESTAMP NULL, 
    start_time TIMESTAMP NULL, 
    end_time TIMESTAMP NULL, 
    total_run_time DATETIME NOT NULL DEFAULT '0', 
    id CHAR(36) NOT NULL DEFAULT (UUID()), 
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    CONSTRAINT pk_flow_run PRIMARY KEY (id), 
    CONSTRAINT fk_flow_run__infrastructure_document_id__block_document FOREIGN KEY(infrastructure_document_id) REFERENCES block_document (id) ON DELETE CASCADE, 
    CONSTRAINT fk_flow_run__flow_id__flow FOREIGN KEY(flow_id) REFERENCES flow (id) ON DELETE cascade, 
    CONSTRAINT fk_flow_run__work_queue_id__work_queue FOREIGN KEY(work_queue_id) REFERENCES work_queue (id) ON DELETE SET NULL
);

CREATE INDEX ix_flow_run__end_time_desc ON flow_run (end_time DESC);

CREATE INDEX ix_flow_run_infrastructure_document_id ON flow_run (infrastructure_document_id);

CREATE INDEX ix_flow_run__scheduler_deployment_id_auto_scheduled_next_schedu ON flow_run (deployment_id, auto_scheduled, next_scheduled_start_time);

CREATE INDEX ix_flow_run_parent_task_run_id ON flow_run (parent_task_run_id);

CREATE INDEX ix_flow_run__state_type ON flow_run (state_type);

CREATE INDEX ix_flow_run__expected_start_time_desc ON flow_run (expected_start_time DESC);

CREATE UNIQUE INDEX uq_flow_run__flow_id_idempotency_key ON flow_run (flow_id, idempotency_key);

CREATE INDEX ix_flow_run_state_id ON flow_run (state_id);

CREATE INDEX ix_flow_run__coalesce_start_time_expected_start_time_desc ON flow_run (coalesce(start_time, expected_start_time) DESC);

CREATE INDEX ix_flow_run_work_queue_id ON flow_run (work_queue_id);

CREATE INDEX ix_flow_run_name ON flow_run (name);

CREATE INDEX ix_flow_run__start_time ON flow_run (start_time);

CREATE INDEX ix_flow_run__coalesce_start_time_expected_start_time_asc ON flow_run (coalesce(start_time, expected_start_time) ASC);

CREATE INDEX ix_flow_run_flow_id ON flow_run (flow_id);

CREATE INDEX ix_flow_run__next_scheduled_start_time_asc ON flow_run (next_scheduled_start_time ASC);

CREATE INDEX ix_flow_run__state_timestamp ON flow_run (state_timestamp);

CREATE INDEX ix_flow_run_work_queue_name ON flow_run (work_queue_name);

CREATE INDEX trgm_ix_flow_run_name ON flow_run (name);

CREATE INDEX ix_flow_run_flow_version ON flow_run (flow_version);

CREATE INDEX ix_flow_run_updated ON flow_run (updated);

CREATE INDEX ix_flow_run_deployment_version ON flow_run (deployment_version);

CREATE INDEX ix_flow_run__state_name ON flow_run (state_name);

CREATE TABLE deployment_schedule (
    deployment_id CHAR(36) NOT NULL, 
    schedule JSON NOT NULL, 
    active BOOL NOT NULL, 
    max_scheduled_runs INTEGER, 
    parameters JSON NOT NULL, 
    slug VARCHAR(255), 
    id CHAR(36) NOT NULL DEFAULT (UUID()), 
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    CONSTRAINT pk_deployment_schedule PRIMARY KEY (id), 
    CONSTRAINT fk_deployment_schedule__deployment_id__deployment FOREIGN KEY(deployment_id) REFERENCES deployment (id) ON DELETE CASCADE
);

CREATE INDEX ix_deployment_schedule_deployment_id ON deployment_schedule (deployment_id);

CREATE INDEX ix_deployment_schedule__slug ON deployment_schedule (slug);

CREATE UNIQUE INDEX ix_deployment_schedule__deployment_id__slug ON deployment_schedule (deployment_id, slug);

CREATE INDEX ix_deployment_schedule_updated ON deployment_schedule (updated);

CREATE TABLE flow_run_input (
    flow_run_id CHAR(36) NOT NULL, 
    `key` VARCHAR(255) NOT NULL, 
    value TEXT NOT NULL, 
    sender VARCHAR(255), 
    id CHAR(36) NOT NULL DEFAULT (UUID()), 
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    CONSTRAINT pk_flow_run_input PRIMARY KEY (id), 
    CONSTRAINT fk_flow_run_input__flow_run_id__flow_run FOREIGN KEY(flow_run_id) REFERENCES flow_run (id) ON DELETE cascade, 
    CONSTRAINT uq_flow_run_input__flow_run_id_key UNIQUE (flow_run_id, `key`)
);

CREATE INDEX ix_flow_run_input_updated ON flow_run_input (updated);

CREATE TABLE flow_run_state (
    flow_run_id CHAR(36) NOT NULL, 
    type ENUM('SCHEDULED','PENDING','RUNNING','COMPLETED','FAILED','CANCELLED','CRASHED','PAUSED','CANCELLING') NOT NULL, 
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    name VARCHAR(255) NOT NULL, 
    message VARCHAR(255), 
    state_details JSON NOT NULL, 
    data JSON, 
    result_artifact_id CHAR(36), 
    id CHAR(36) NOT NULL DEFAULT (UUID()), 
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    CONSTRAINT pk_flow_run_state PRIMARY KEY (id), 
    CONSTRAINT fk_flow_run_state__flow_run_id__flow_run FOREIGN KEY(flow_run_id) REFERENCES flow_run (id) ON DELETE cascade
);

CREATE INDEX ix_flow_run_state_name ON flow_run_state (name);

CREATE INDEX ix_flow_run_state_result_artifact_id ON flow_run_state (result_artifact_id);

CREATE UNIQUE INDEX uq_flow_run_state__flow_run_id_timestamp_desc ON flow_run_state (flow_run_id, timestamp DESC);

CREATE INDEX ix_flow_run_state_type ON flow_run_state (type);

CREATE INDEX ix_flow_run_state_updated ON flow_run_state (updated);

CREATE TABLE task_run (
    flow_run_id CHAR(36), 
    task_key VARCHAR(255) NOT NULL, 
    dynamic_key VARCHAR(255) NOT NULL, 
    cache_key VARCHAR(255), 
    cache_expiration TIMESTAMP NULL, 
    task_version VARCHAR(255), 
    flow_run_run_count INTEGER NOT NULL DEFAULT '0', 
    empirical_policy JSON NOT NULL, 
    task_inputs JSON NOT NULL, 
    tags JSON NOT NULL, 
    labels JSON, 
    state_id CHAR(36), 
    name VARCHAR(255) NOT NULL, 
    state_type ENUM('SCHEDULED','PENDING','RUNNING','COMPLETED','FAILED','CANCELLED','CRASHED','PAUSED','CANCELLING'), 
    state_name VARCHAR(255), 
    state_timestamp TIMESTAMP NULL, 
    run_count INTEGER NOT NULL DEFAULT '0', 
    expected_start_time TIMESTAMP NULL, 
    next_scheduled_start_time TIMESTAMP NULL, 
    start_time TIMESTAMP NULL, 
    end_time TIMESTAMP NULL, 
    total_run_time DATETIME NOT NULL DEFAULT '0', 
    id CHAR(36) NOT NULL DEFAULT (UUID()), 
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    CONSTRAINT pk_task_run PRIMARY KEY (id), 
    CONSTRAINT fk_task_run__flow_run_id__flow_run FOREIGN KEY(flow_run_id) REFERENCES flow_run (id) ON DELETE cascade
);

CREATE INDEX ix_task_run__state_name ON task_run (state_name);

CREATE INDEX ix_task_run_name ON task_run (name);

CREATE INDEX ix_task_run__state_type_start_time ON task_run (state_type, start_time);

CREATE INDEX ix_task_run__state_timestamp ON task_run (state_timestamp);

CREATE INDEX ix_task_run__start_time ON task_run (start_time);

CREATE INDEX ix_task_run__end_time_desc ON task_run (end_time DESC);

CREATE UNIQUE INDEX uq_task_run__flow_run_id_task_key_dynamic_key ON task_run (flow_run_id, task_key, dynamic_key);

CREATE INDEX ix_task_run__expected_start_time_desc ON task_run (expected_start_time DESC);

CREATE INDEX trgm_ix_task_run_name ON task_run (name);

CREATE INDEX ix_task_run_updated ON task_run (updated);

CREATE INDEX ix_task_run_flow_run_id ON task_run (flow_run_id);

CREATE INDEX ix_task_run__state_type ON task_run (state_type);

CREATE INDEX ix_task_run__next_scheduled_start_time_asc ON task_run (next_scheduled_start_time ASC);

CREATE INDEX ix_task_run_state_id ON task_run (state_id);

CREATE TABLE task_run_state (
    task_run_id CHAR(36) NOT NULL, 
    type ENUM('SCHEDULED','PENDING','RUNNING','COMPLETED','FAILED','CANCELLED','CRASHED','PAUSED','CANCELLING') NOT NULL, 
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    name VARCHAR(255) NOT NULL, 
    message VARCHAR(255), 
    state_details JSON NOT NULL, 
    data JSON, 
    result_artifact_id CHAR(36), 
    id CHAR(36) NOT NULL DEFAULT (UUID()), 
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
    CONSTRAINT pk_task_run_state PRIMARY KEY (id), 
    CONSTRAINT fk_task_run_state__task_run_id__task_run FOREIGN KEY(task_run_id) REFERENCES task_run (id) ON DELETE cascade
);

CREATE INDEX ix_task_run_state_type ON task_run_state (type);

CREATE INDEX ix_task_run_state_name ON task_run_state (name);

CREATE INDEX ix_task_run_state_updated ON task_run_state (updated);

CREATE UNIQUE INDEX uq_task_run_state__task_run_id_timestamp_desc ON task_run_state (task_run_id, timestamp DESC);

CREATE INDEX ix_task_run_state_result_artifact_id ON task_run_state (result_artifact_id);

ALTER TABLE work_pool ADD CONSTRAINT fk_work_pool__default_queue_id__work_queue FOREIGN KEY(default_queue_id) REFERENCES work_queue (id) ON DELETE RESTRICT;

ALTER TABLE flow_run ADD CONSTRAINT fk_flow_run__state_id__flow_run_state FOREIGN KEY(state_id) REFERENCES flow_run_state (id) ON DELETE SET NULL;

ALTER TABLE flow_run_state ADD CONSTRAINT fk_flow_run_state__result_artifact_id__artifact FOREIGN KEY(result_artifact_id) REFERENCES artifact (id) ON DELETE SET NULL;

ALTER TABLE flow_run ADD CONSTRAINT fk_flow_run__parent_task_run_id__task_run FOREIGN KEY(parent_task_run_id) REFERENCES task_run (id) ON DELETE SET NULL;

ALTER TABLE task_run_state ADD CONSTRAINT fk_task_run_state__result_artifact_id__artifact FOREIGN KEY(result_artifact_id) REFERENCES artifact (id) ON DELETE SET NULL;

INSERT INTO alembic_version (version_num) VALUES ('3d1b2a5f0f1a');

