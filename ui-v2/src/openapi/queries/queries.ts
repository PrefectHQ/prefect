// generated with @7nohe/openapi-react-query-codegen@1.6.2 

import { UseMutationOptions, UseQueryOptions, useMutation, useQuery } from "@tanstack/react-query";
import { AdminService, ArtifactsService, AutomationsService, BlockCapabilitiesService, BlockDocumentsService, BlockSchemasService, BlockTypesService, CollectionsService, ConcurrencyLimitsService, ConcurrencyLimitsV2Service, DefaultService, DeploymentsService, EventsService, FlowRunNotificationPoliciesService, FlowRunStatesService, FlowRunsService, FlowsService, LogsService, RootService, SavedSearchesService, SchemasService, TaskRunStatesService, TaskRunsService, TaskWorkersService, UiService, VariablesService, WorkPoolsService, WorkQueuesService } from "../requests/services.gen";
import { ArtifactCreate, ArtifactUpdate, AutomationCreate, AutomationPartialUpdate, AutomationUpdate, BlockDocumentCreate, BlockDocumentUpdate, BlockSchemaCreate, BlockTypeCreate, BlockTypeUpdate, Body_average_flow_run_lateness_flow_runs_lateness_post, Body_bulk_decrement_active_slots_v2_concurrency_limits_decrement_post, Body_bulk_increment_active_slots_v2_concurrency_limits_increment_post, Body_clear_database_admin_database_clear_post, Body_count_account_events_events_count_by__countable__post, Body_count_artifacts_artifacts_count_post, Body_count_block_documents_block_documents_count_post, Body_count_deployments_by_flow_ui_flows_count_deployments_post, Body_count_deployments_deployments_count_post, Body_count_flow_runs_flow_runs_count_post, Body_count_flows_flows_count_post, Body_count_latest_artifacts_artifacts_latest_count_post, Body_count_task_runs_by_flow_run_ui_flow_runs_count_task_runs_post, Body_count_task_runs_task_runs_count_post, Body_count_variables_variables_count_post, Body_count_work_pools_work_pools_count_post, Body_create_database_admin_database_create_post, Body_create_flow_run_input_flow_runs__id__input_post, Body_decrement_concurrency_limits_v1_concurrency_limits_decrement_post, Body_drop_database_admin_database_drop_post, Body_filter_flow_run_input_flow_runs__id__input_filter_post, Body_flow_run_history_flow_runs_history_post, Body_get_scheduled_flow_runs_for_deployments_deployments_get_scheduled_flow_runs_post, Body_get_scheduled_flow_runs_work_pools__name__get_scheduled_flow_runs_post, Body_increment_concurrency_limits_v1_concurrency_limits_increment_post, Body_next_runs_by_flow_ui_flows_next_runs_post, Body_paginate_deployments_deployments_paginate_post, Body_paginate_flow_runs_flow_runs_paginate_post, Body_paginate_flows_flows_paginate_post, Body_read_all_concurrency_limits_v2_v2_concurrency_limits_filter_post, Body_read_artifacts_artifacts_filter_post, Body_read_automations_automations_filter_post, Body_read_block_documents_block_documents_filter_post, Body_read_block_schemas_block_schemas_filter_post, Body_read_block_types_block_types_filter_post, Body_read_concurrency_limits_concurrency_limits_filter_post, Body_read_dashboard_task_run_counts_ui_task_runs_dashboard_counts_post, Body_read_deployments_deployments_filter_post, Body_read_events_events_filter_post, Body_read_flow_run_history_ui_flow_runs_history_post, Body_read_flow_run_notification_policies_flow_run_notification_policies_filter_post, Body_read_flow_runs_flow_runs_filter_post, Body_read_flows_flows_filter_post, Body_read_latest_artifacts_artifacts_latest_filter_post, Body_read_logs_logs_filter_post, Body_read_saved_searches_saved_searches_filter_post, Body_read_task_run_counts_by_state_ui_task_runs_count_post, Body_read_task_runs_task_runs_filter_post, Body_read_task_workers_task_workers_filter_post, Body_read_variables_variables_filter_post, Body_read_work_pools_work_pools_filter_post, Body_read_work_queue_runs_work_queues__id__get_runs_post, Body_read_work_queues_work_pools__work_pool_name__queues_filter_post, Body_read_work_queues_work_queues_filter_post, Body_read_workers_work_pools__work_pool_name__workers_filter_post, Body_reset_concurrency_limit_by_tag_concurrency_limits_tag__tag__reset_post, Body_resume_flow_run_flow_runs__id__resume_post, Body_schedule_deployment_deployments__id__schedule_post, Body_set_flow_run_state_flow_runs__id__set_state_post, Body_set_task_run_state_task_runs__id__set_state_post, Body_task_run_history_task_runs_history_post, Body_validate_obj_ui_schemas_validate_post, Body_worker_heartbeat_work_pools__work_pool_name__workers_heartbeat_post, ConcurrencyLimitCreate, ConcurrencyLimitV2Create, ConcurrencyLimitV2Update, Countable, DeploymentCreate, DeploymentFlowRunCreate, DeploymentScheduleCreate, DeploymentScheduleUpdate, DeploymentUpdate, Event, FlowCreate, FlowRunCreate, FlowRunNotificationPolicyCreate, FlowRunNotificationPolicyUpdate, FlowRunUpdate, FlowUpdate, LogCreate, SavedSearchCreate, TaskRunCreate, TaskRunUpdate, VariableCreate, VariableUpdate, WorkPoolCreate, WorkPoolUpdate, WorkQueueCreate, WorkQueueUpdate } from "../requests/types.gen";
import * as Common from "./common";
export const useRootServiceGetHealth = <TData = Common.RootServiceGetHealthDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>(queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useQuery<TData, TError>({ queryKey: Common.UseRootServiceGetHealthKeyFn(queryKey), queryFn: () => RootService.getHealth() as TData, ...options });
export const useRootServiceGetVersion = <TData = Common.RootServiceGetVersionDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>(queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useQuery<TData, TError>({ queryKey: Common.UseRootServiceGetVersionKeyFn(queryKey), queryFn: () => RootService.getVersion() as TData, ...options });
export const useRootServiceGetHello = <TData = Common.RootServiceGetHelloDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ xPrefectApiVersion }: {
  xPrefectApiVersion?: string;
} = {}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useQuery<TData, TError>({ queryKey: Common.UseRootServiceGetHelloKeyFn({ xPrefectApiVersion }, queryKey), queryFn: () => RootService.getHello({ xPrefectApiVersion }) as TData, ...options });
export const useRootServiceGetReady = <TData = Common.RootServiceGetReadyDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ xPrefectApiVersion }: {
  xPrefectApiVersion?: string;
} = {}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useQuery<TData, TError>({ queryKey: Common.UseRootServiceGetReadyKeyFn({ xPrefectApiVersion }, queryKey), queryFn: () => RootService.getReady({ xPrefectApiVersion }) as TData, ...options });
export const useFlowsServiceGetFlowsById = <TData = Common.FlowsServiceGetFlowsByIdDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useQuery<TData, TError>({ queryKey: Common.UseFlowsServiceGetFlowsByIdKeyFn({ id, xPrefectApiVersion }, queryKey), queryFn: () => FlowsService.getFlowsById({ id, xPrefectApiVersion }) as TData, ...options });
export const useFlowsServiceGetFlowsNameByName = <TData = Common.FlowsServiceGetFlowsNameByNameDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ name, xPrefectApiVersion }: {
  name: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useQuery<TData, TError>({ queryKey: Common.UseFlowsServiceGetFlowsNameByNameKeyFn({ name, xPrefectApiVersion }, queryKey), queryFn: () => FlowsService.getFlowsNameByName({ name, xPrefectApiVersion }) as TData, ...options });
export const useFlowRunsServiceGetFlowRunsById = <TData = Common.FlowRunsServiceGetFlowRunsByIdDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useQuery<TData, TError>({ queryKey: Common.UseFlowRunsServiceGetFlowRunsByIdKeyFn({ id, xPrefectApiVersion }, queryKey), queryFn: () => FlowRunsService.getFlowRunsById({ id, xPrefectApiVersion }) as TData, ...options });
export const useFlowRunsServiceGetFlowRunsByIdGraph = <TData = Common.FlowRunsServiceGetFlowRunsByIdGraphDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useQuery<TData, TError>({ queryKey: Common.UseFlowRunsServiceGetFlowRunsByIdGraphKeyFn({ id, xPrefectApiVersion }, queryKey), queryFn: () => FlowRunsService.getFlowRunsByIdGraph({ id, xPrefectApiVersion }) as TData, ...options });
export const useFlowRunsServiceGetFlowRunsByIdGraphV2 = <TData = Common.FlowRunsServiceGetFlowRunsByIdGraphV2DefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ id, since, xPrefectApiVersion }: {
  id: string;
  since?: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useQuery<TData, TError>({ queryKey: Common.UseFlowRunsServiceGetFlowRunsByIdGraphV2KeyFn({ id, since, xPrefectApiVersion }, queryKey), queryFn: () => FlowRunsService.getFlowRunsByIdGraphV2({ id, since, xPrefectApiVersion }) as TData, ...options });
export const useFlowRunsServiceGetFlowRunsByIdInputByKey = <TData = Common.FlowRunsServiceGetFlowRunsByIdInputByKeyDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ id, key, xPrefectApiVersion }: {
  id: string;
  key: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useQuery<TData, TError>({ queryKey: Common.UseFlowRunsServiceGetFlowRunsByIdInputByKeyKeyFn({ id, key, xPrefectApiVersion }, queryKey), queryFn: () => FlowRunsService.getFlowRunsByIdInputByKey({ id, key, xPrefectApiVersion }) as TData, ...options });
export const useFlowRunsServiceGetFlowRunsByIdLogsDownload = <TData = Common.FlowRunsServiceGetFlowRunsByIdLogsDownloadDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useQuery<TData, TError>({ queryKey: Common.UseFlowRunsServiceGetFlowRunsByIdLogsDownloadKeyFn({ id, xPrefectApiVersion }, queryKey), queryFn: () => FlowRunsService.getFlowRunsByIdLogsDownload({ id, xPrefectApiVersion }) as TData, ...options });
export const useTaskRunsServiceGetTaskRunsById = <TData = Common.TaskRunsServiceGetTaskRunsByIdDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useQuery<TData, TError>({ queryKey: Common.UseTaskRunsServiceGetTaskRunsByIdKeyFn({ id, xPrefectApiVersion }, queryKey), queryFn: () => TaskRunsService.getTaskRunsById({ id, xPrefectApiVersion }) as TData, ...options });
export const useFlowRunStatesServiceGetFlowRunStatesById = <TData = Common.FlowRunStatesServiceGetFlowRunStatesByIdDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useQuery<TData, TError>({ queryKey: Common.UseFlowRunStatesServiceGetFlowRunStatesByIdKeyFn({ id, xPrefectApiVersion }, queryKey), queryFn: () => FlowRunStatesService.getFlowRunStatesById({ id, xPrefectApiVersion }) as TData, ...options });
export const useFlowRunStatesServiceGetFlowRunStates = <TData = Common.FlowRunStatesServiceGetFlowRunStatesDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ flowRunId, xPrefectApiVersion }: {
  flowRunId: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useQuery<TData, TError>({ queryKey: Common.UseFlowRunStatesServiceGetFlowRunStatesKeyFn({ flowRunId, xPrefectApiVersion }, queryKey), queryFn: () => FlowRunStatesService.getFlowRunStates({ flowRunId, xPrefectApiVersion }) as TData, ...options });
export const useTaskRunStatesServiceGetTaskRunStatesById = <TData = Common.TaskRunStatesServiceGetTaskRunStatesByIdDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useQuery<TData, TError>({ queryKey: Common.UseTaskRunStatesServiceGetTaskRunStatesByIdKeyFn({ id, xPrefectApiVersion }, queryKey), queryFn: () => TaskRunStatesService.getTaskRunStatesById({ id, xPrefectApiVersion }) as TData, ...options });
export const useTaskRunStatesServiceGetTaskRunStates = <TData = Common.TaskRunStatesServiceGetTaskRunStatesDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ taskRunId, xPrefectApiVersion }: {
  taskRunId: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useQuery<TData, TError>({ queryKey: Common.UseTaskRunStatesServiceGetTaskRunStatesKeyFn({ taskRunId, xPrefectApiVersion }, queryKey), queryFn: () => TaskRunStatesService.getTaskRunStates({ taskRunId, xPrefectApiVersion }) as TData, ...options });
export const useFlowRunNotificationPoliciesServiceGetFlowRunNotificationPoliciesById = <TData = Common.FlowRunNotificationPoliciesServiceGetFlowRunNotificationPoliciesByIdDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useQuery<TData, TError>({ queryKey: Common.UseFlowRunNotificationPoliciesServiceGetFlowRunNotificationPoliciesByIdKeyFn({ id, xPrefectApiVersion }, queryKey), queryFn: () => FlowRunNotificationPoliciesService.getFlowRunNotificationPoliciesById({ id, xPrefectApiVersion }) as TData, ...options });
export const useDeploymentsServiceGetDeploymentsById = <TData = Common.DeploymentsServiceGetDeploymentsByIdDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useQuery<TData, TError>({ queryKey: Common.UseDeploymentsServiceGetDeploymentsByIdKeyFn({ id, xPrefectApiVersion }, queryKey), queryFn: () => DeploymentsService.getDeploymentsById({ id, xPrefectApiVersion }) as TData, ...options });
export const useDeploymentsServiceGetDeploymentsNameByFlowNameByDeploymentName = <TData = Common.DeploymentsServiceGetDeploymentsNameByFlowNameByDeploymentNameDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ deploymentName, flowName, xPrefectApiVersion }: {
  deploymentName: string;
  flowName: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useQuery<TData, TError>({ queryKey: Common.UseDeploymentsServiceGetDeploymentsNameByFlowNameByDeploymentNameKeyFn({ deploymentName, flowName, xPrefectApiVersion }, queryKey), queryFn: () => DeploymentsService.getDeploymentsNameByFlowNameByDeploymentName({ deploymentName, flowName, xPrefectApiVersion }) as TData, ...options });
export const useDeploymentsServiceGetDeploymentsByIdWorkQueueCheck = <TData = Common.DeploymentsServiceGetDeploymentsByIdWorkQueueCheckDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useQuery<TData, TError>({ queryKey: Common.UseDeploymentsServiceGetDeploymentsByIdWorkQueueCheckKeyFn({ id, xPrefectApiVersion }, queryKey), queryFn: () => DeploymentsService.getDeploymentsByIdWorkQueueCheck({ id, xPrefectApiVersion }) as TData, ...options });
export const useDeploymentsServiceGetDeploymentsByIdSchedules = <TData = Common.DeploymentsServiceGetDeploymentsByIdSchedulesDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useQuery<TData, TError>({ queryKey: Common.UseDeploymentsServiceGetDeploymentsByIdSchedulesKeyFn({ id, xPrefectApiVersion }, queryKey), queryFn: () => DeploymentsService.getDeploymentsByIdSchedules({ id, xPrefectApiVersion }) as TData, ...options });
export const useSavedSearchesServiceGetSavedSearchesById = <TData = Common.SavedSearchesServiceGetSavedSearchesByIdDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useQuery<TData, TError>({ queryKey: Common.UseSavedSearchesServiceGetSavedSearchesByIdKeyFn({ id, xPrefectApiVersion }, queryKey), queryFn: () => SavedSearchesService.getSavedSearchesById({ id, xPrefectApiVersion }) as TData, ...options });
export const useConcurrencyLimitsServiceGetConcurrencyLimitsById = <TData = Common.ConcurrencyLimitsServiceGetConcurrencyLimitsByIdDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useQuery<TData, TError>({ queryKey: Common.UseConcurrencyLimitsServiceGetConcurrencyLimitsByIdKeyFn({ id, xPrefectApiVersion }, queryKey), queryFn: () => ConcurrencyLimitsService.getConcurrencyLimitsById({ id, xPrefectApiVersion }) as TData, ...options });
export const useConcurrencyLimitsServiceGetConcurrencyLimitsTagByTag = <TData = Common.ConcurrencyLimitsServiceGetConcurrencyLimitsTagByTagDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ tag, xPrefectApiVersion }: {
  tag: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useQuery<TData, TError>({ queryKey: Common.UseConcurrencyLimitsServiceGetConcurrencyLimitsTagByTagKeyFn({ tag, xPrefectApiVersion }, queryKey), queryFn: () => ConcurrencyLimitsService.getConcurrencyLimitsTagByTag({ tag, xPrefectApiVersion }) as TData, ...options });
export const useConcurrencyLimitsV2ServiceGetV2ConcurrencyLimitsByIdOrName = <TData = Common.ConcurrencyLimitsV2ServiceGetV2ConcurrencyLimitsByIdOrNameDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ idOrName, xPrefectApiVersion }: {
  idOrName: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useQuery<TData, TError>({ queryKey: Common.UseConcurrencyLimitsV2ServiceGetV2ConcurrencyLimitsByIdOrNameKeyFn({ idOrName, xPrefectApiVersion }, queryKey), queryFn: () => ConcurrencyLimitsV2Service.getV2ConcurrencyLimitsByIdOrName({ idOrName, xPrefectApiVersion }) as TData, ...options });
export const useBlockTypesServiceGetBlockTypesById = <TData = Common.BlockTypesServiceGetBlockTypesByIdDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useQuery<TData, TError>({ queryKey: Common.UseBlockTypesServiceGetBlockTypesByIdKeyFn({ id, xPrefectApiVersion }, queryKey), queryFn: () => BlockTypesService.getBlockTypesById({ id, xPrefectApiVersion }) as TData, ...options });
export const useBlockTypesServiceGetBlockTypesSlugBySlug = <TData = Common.BlockTypesServiceGetBlockTypesSlugBySlugDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ slug, xPrefectApiVersion }: {
  slug: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useQuery<TData, TError>({ queryKey: Common.UseBlockTypesServiceGetBlockTypesSlugBySlugKeyFn({ slug, xPrefectApiVersion }, queryKey), queryFn: () => BlockTypesService.getBlockTypesSlugBySlug({ slug, xPrefectApiVersion }) as TData, ...options });
export const useBlockTypesServiceGetBlockTypesSlugBySlugBlockDocuments = <TData = Common.BlockTypesServiceGetBlockTypesSlugBySlugBlockDocumentsDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ includeSecrets, slug, xPrefectApiVersion }: {
  includeSecrets?: boolean;
  slug: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useQuery<TData, TError>({ queryKey: Common.UseBlockTypesServiceGetBlockTypesSlugBySlugBlockDocumentsKeyFn({ includeSecrets, slug, xPrefectApiVersion }, queryKey), queryFn: () => BlockTypesService.getBlockTypesSlugBySlugBlockDocuments({ includeSecrets, slug, xPrefectApiVersion }) as TData, ...options });
export const useBlockTypesServiceGetBlockTypesSlugBySlugBlockDocumentsNameByBlockDocumentName = <TData = Common.BlockTypesServiceGetBlockTypesSlugBySlugBlockDocumentsNameByBlockDocumentNameDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ blockDocumentName, includeSecrets, slug, xPrefectApiVersion }: {
  blockDocumentName: string;
  includeSecrets?: boolean;
  slug: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useQuery<TData, TError>({ queryKey: Common.UseBlockTypesServiceGetBlockTypesSlugBySlugBlockDocumentsNameByBlockDocumentNameKeyFn({ blockDocumentName, includeSecrets, slug, xPrefectApiVersion }, queryKey), queryFn: () => BlockTypesService.getBlockTypesSlugBySlugBlockDocumentsNameByBlockDocumentName({ blockDocumentName, includeSecrets, slug, xPrefectApiVersion }) as TData, ...options });
export const useBlockDocumentsServiceGetBlockTypesSlugBySlugBlockDocuments = <TData = Common.BlockDocumentsServiceGetBlockTypesSlugBySlugBlockDocumentsDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ includeSecrets, slug, xPrefectApiVersion }: {
  includeSecrets?: boolean;
  slug: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useQuery<TData, TError>({ queryKey: Common.UseBlockDocumentsServiceGetBlockTypesSlugBySlugBlockDocumentsKeyFn({ includeSecrets, slug, xPrefectApiVersion }, queryKey), queryFn: () => BlockDocumentsService.getBlockTypesSlugBySlugBlockDocuments({ includeSecrets, slug, xPrefectApiVersion }) as TData, ...options });
export const useBlockDocumentsServiceGetBlockTypesSlugBySlugBlockDocumentsNameByBlockDocumentName = <TData = Common.BlockDocumentsServiceGetBlockTypesSlugBySlugBlockDocumentsNameByBlockDocumentNameDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ blockDocumentName, includeSecrets, slug, xPrefectApiVersion }: {
  blockDocumentName: string;
  includeSecrets?: boolean;
  slug: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useQuery<TData, TError>({ queryKey: Common.UseBlockDocumentsServiceGetBlockTypesSlugBySlugBlockDocumentsNameByBlockDocumentNameKeyFn({ blockDocumentName, includeSecrets, slug, xPrefectApiVersion }, queryKey), queryFn: () => BlockDocumentsService.getBlockTypesSlugBySlugBlockDocumentsNameByBlockDocumentName({ blockDocumentName, includeSecrets, slug, xPrefectApiVersion }) as TData, ...options });
export const useBlockDocumentsServiceGetBlockDocumentsById = <TData = Common.BlockDocumentsServiceGetBlockDocumentsByIdDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ id, includeSecrets, xPrefectApiVersion }: {
  id: string;
  includeSecrets?: boolean;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useQuery<TData, TError>({ queryKey: Common.UseBlockDocumentsServiceGetBlockDocumentsByIdKeyFn({ id, includeSecrets, xPrefectApiVersion }, queryKey), queryFn: () => BlockDocumentsService.getBlockDocumentsById({ id, includeSecrets, xPrefectApiVersion }) as TData, ...options });
export const useWorkPoolsServiceGetWorkPoolsByName = <TData = Common.WorkPoolsServiceGetWorkPoolsByNameDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ name, xPrefectApiVersion }: {
  name: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useQuery<TData, TError>({ queryKey: Common.UseWorkPoolsServiceGetWorkPoolsByNameKeyFn({ name, xPrefectApiVersion }, queryKey), queryFn: () => WorkPoolsService.getWorkPoolsByName({ name, xPrefectApiVersion }) as TData, ...options });
export const useWorkPoolsServiceGetWorkPoolsByWorkPoolNameQueuesByName = <TData = Common.WorkPoolsServiceGetWorkPoolsByWorkPoolNameQueuesByNameDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ name, workPoolName, xPrefectApiVersion }: {
  name: string;
  workPoolName: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useQuery<TData, TError>({ queryKey: Common.UseWorkPoolsServiceGetWorkPoolsByWorkPoolNameQueuesByNameKeyFn({ name, workPoolName, xPrefectApiVersion }, queryKey), queryFn: () => WorkPoolsService.getWorkPoolsByWorkPoolNameQueuesByName({ name, workPoolName, xPrefectApiVersion }) as TData, ...options });
export const useWorkQueuesServiceGetWorkQueuesById = <TData = Common.WorkQueuesServiceGetWorkQueuesByIdDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useQuery<TData, TError>({ queryKey: Common.UseWorkQueuesServiceGetWorkQueuesByIdKeyFn({ id, xPrefectApiVersion }, queryKey), queryFn: () => WorkQueuesService.getWorkQueuesById({ id, xPrefectApiVersion }) as TData, ...options });
export const useWorkQueuesServiceGetWorkQueuesNameByName = <TData = Common.WorkQueuesServiceGetWorkQueuesNameByNameDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ name, xPrefectApiVersion }: {
  name: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useQuery<TData, TError>({ queryKey: Common.UseWorkQueuesServiceGetWorkQueuesNameByNameKeyFn({ name, xPrefectApiVersion }, queryKey), queryFn: () => WorkQueuesService.getWorkQueuesNameByName({ name, xPrefectApiVersion }) as TData, ...options });
export const useWorkQueuesServiceGetWorkQueuesByIdStatus = <TData = Common.WorkQueuesServiceGetWorkQueuesByIdStatusDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useQuery<TData, TError>({ queryKey: Common.UseWorkQueuesServiceGetWorkQueuesByIdStatusKeyFn({ id, xPrefectApiVersion }, queryKey), queryFn: () => WorkQueuesService.getWorkQueuesByIdStatus({ id, xPrefectApiVersion }) as TData, ...options });
export const useArtifactsServiceGetArtifactsById = <TData = Common.ArtifactsServiceGetArtifactsByIdDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useQuery<TData, TError>({ queryKey: Common.UseArtifactsServiceGetArtifactsByIdKeyFn({ id, xPrefectApiVersion }, queryKey), queryFn: () => ArtifactsService.getArtifactsById({ id, xPrefectApiVersion }) as TData, ...options });
export const useArtifactsServiceGetArtifactsByKeyLatest = <TData = Common.ArtifactsServiceGetArtifactsByKeyLatestDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ key, xPrefectApiVersion }: {
  key: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useQuery<TData, TError>({ queryKey: Common.UseArtifactsServiceGetArtifactsByKeyLatestKeyFn({ key, xPrefectApiVersion }, queryKey), queryFn: () => ArtifactsService.getArtifactsByKeyLatest({ key, xPrefectApiVersion }) as TData, ...options });
export const useBlockSchemasServiceGetBlockSchemasById = <TData = Common.BlockSchemasServiceGetBlockSchemasByIdDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useQuery<TData, TError>({ queryKey: Common.UseBlockSchemasServiceGetBlockSchemasByIdKeyFn({ id, xPrefectApiVersion }, queryKey), queryFn: () => BlockSchemasService.getBlockSchemasById({ id, xPrefectApiVersion }) as TData, ...options });
export const useBlockSchemasServiceGetBlockSchemasChecksumByChecksum = <TData = Common.BlockSchemasServiceGetBlockSchemasChecksumByChecksumDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ checksum, version, xPrefectApiVersion }: {
  checksum: string;
  version?: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useQuery<TData, TError>({ queryKey: Common.UseBlockSchemasServiceGetBlockSchemasChecksumByChecksumKeyFn({ checksum, version, xPrefectApiVersion }, queryKey), queryFn: () => BlockSchemasService.getBlockSchemasChecksumByChecksum({ checksum, version, xPrefectApiVersion }) as TData, ...options });
export const useBlockCapabilitiesServiceGetBlockCapabilities = <TData = Common.BlockCapabilitiesServiceGetBlockCapabilitiesDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ xPrefectApiVersion }: {
  xPrefectApiVersion?: string;
} = {}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useQuery<TData, TError>({ queryKey: Common.UseBlockCapabilitiesServiceGetBlockCapabilitiesKeyFn({ xPrefectApiVersion }, queryKey), queryFn: () => BlockCapabilitiesService.getBlockCapabilities({ xPrefectApiVersion }) as TData, ...options });
export const useCollectionsServiceGetCollectionsViewsByView = <TData = Common.CollectionsServiceGetCollectionsViewsByViewDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ view, xPrefectApiVersion }: {
  view: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useQuery<TData, TError>({ queryKey: Common.UseCollectionsServiceGetCollectionsViewsByViewKeyFn({ view, xPrefectApiVersion }, queryKey), queryFn: () => CollectionsService.getCollectionsViewsByView({ view, xPrefectApiVersion }) as TData, ...options });
export const useVariablesServiceGetVariablesById = <TData = Common.VariablesServiceGetVariablesByIdDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useQuery<TData, TError>({ queryKey: Common.UseVariablesServiceGetVariablesByIdKeyFn({ id, xPrefectApiVersion }, queryKey), queryFn: () => VariablesService.getVariablesById({ id, xPrefectApiVersion }) as TData, ...options });
export const useVariablesServiceGetVariablesNameByName = <TData = Common.VariablesServiceGetVariablesNameByNameDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ name, xPrefectApiVersion }: {
  name: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useQuery<TData, TError>({ queryKey: Common.UseVariablesServiceGetVariablesNameByNameKeyFn({ name, xPrefectApiVersion }, queryKey), queryFn: () => VariablesService.getVariablesNameByName({ name, xPrefectApiVersion }) as TData, ...options });
export const useDefaultServiceGetCsrfToken = <TData = Common.DefaultServiceGetCsrfTokenDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ client, xPrefectApiVersion }: {
  client: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useQuery<TData, TError>({ queryKey: Common.UseDefaultServiceGetCsrfTokenKeyFn({ client, xPrefectApiVersion }, queryKey), queryFn: () => DefaultService.getCsrfToken({ client, xPrefectApiVersion }) as TData, ...options });
export const useEventsServiceGetEventsFilterNext = <TData = Common.EventsServiceGetEventsFilterNextDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ pageToken, xPrefectApiVersion }: {
  pageToken: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useQuery<TData, TError>({ queryKey: Common.UseEventsServiceGetEventsFilterNextKeyFn({ pageToken, xPrefectApiVersion }, queryKey), queryFn: () => EventsService.getEventsFilterNext({ pageToken, xPrefectApiVersion }) as TData, ...options });
export const useAutomationsServiceGetAutomationsById = <TData = Common.AutomationsServiceGetAutomationsByIdDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useQuery<TData, TError>({ queryKey: Common.UseAutomationsServiceGetAutomationsByIdKeyFn({ id, xPrefectApiVersion }, queryKey), queryFn: () => AutomationsService.getAutomationsById({ id, xPrefectApiVersion }) as TData, ...options });
export const useAutomationsServiceGetAutomationsRelatedToByResourceId = <TData = Common.AutomationsServiceGetAutomationsRelatedToByResourceIdDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ resourceId, xPrefectApiVersion }: {
  resourceId: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useQuery<TData, TError>({ queryKey: Common.UseAutomationsServiceGetAutomationsRelatedToByResourceIdKeyFn({ resourceId, xPrefectApiVersion }, queryKey), queryFn: () => AutomationsService.getAutomationsRelatedToByResourceId({ resourceId, xPrefectApiVersion }) as TData, ...options });
export const useAdminServiceGetAdminSettings = <TData = Common.AdminServiceGetAdminSettingsDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ xPrefectApiVersion }: {
  xPrefectApiVersion?: string;
} = {}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useQuery<TData, TError>({ queryKey: Common.UseAdminServiceGetAdminSettingsKeyFn({ xPrefectApiVersion }, queryKey), queryFn: () => AdminService.getAdminSettings({ xPrefectApiVersion }) as TData, ...options });
export const useAdminServiceGetAdminVersion = <TData = Common.AdminServiceGetAdminVersionDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ xPrefectApiVersion }: {
  xPrefectApiVersion?: string;
} = {}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useQuery<TData, TError>({ queryKey: Common.UseAdminServiceGetAdminVersionKeyFn({ xPrefectApiVersion }, queryKey), queryFn: () => AdminService.getAdminVersion({ xPrefectApiVersion }) as TData, ...options });
export const useFlowsServicePostFlows = <TData = Common.FlowsServicePostFlowsMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody: FlowCreate;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody: FlowCreate;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => FlowsService.postFlows({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useFlowsServicePostFlowsCount = <TData = Common.FlowsServicePostFlowsCountMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody?: Body_count_flows_flows_count_post;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody?: Body_count_flows_flows_count_post;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => FlowsService.postFlowsCount({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useFlowsServicePostFlowsFilter = <TData = Common.FlowsServicePostFlowsFilterMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody?: Body_read_flows_flows_filter_post;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody?: Body_read_flows_flows_filter_post;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => FlowsService.postFlowsFilter({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useFlowsServicePostFlowsPaginate = <TData = Common.FlowsServicePostFlowsPaginateMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody?: Body_paginate_flows_flows_paginate_post;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody?: Body_paginate_flows_flows_paginate_post;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => FlowsService.postFlowsPaginate({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useFlowsServicePostUiFlowsCountDeployments = <TData = Common.FlowsServicePostUiFlowsCountDeploymentsMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody: Body_count_deployments_by_flow_ui_flows_count_deployments_post;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody: Body_count_deployments_by_flow_ui_flows_count_deployments_post;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => FlowsService.postUiFlowsCountDeployments({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useFlowsServicePostUiFlowsNextRuns = <TData = Common.FlowsServicePostUiFlowsNextRunsMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody: Body_next_runs_by_flow_ui_flows_next_runs_post;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody: Body_next_runs_by_flow_ui_flows_next_runs_post;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => FlowsService.postUiFlowsNextRuns({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useFlowRunsServicePostFlowRuns = <TData = Common.FlowRunsServicePostFlowRunsMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody: FlowRunCreate;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody: FlowRunCreate;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => FlowRunsService.postFlowRuns({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useFlowRunsServicePostFlowRunsCount = <TData = Common.FlowRunsServicePostFlowRunsCountMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody?: Body_count_flow_runs_flow_runs_count_post;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody?: Body_count_flow_runs_flow_runs_count_post;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => FlowRunsService.postFlowRunsCount({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useFlowRunsServicePostFlowRunsLateness = <TData = Common.FlowRunsServicePostFlowRunsLatenessMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody?: Body_average_flow_run_lateness_flow_runs_lateness_post;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody?: Body_average_flow_run_lateness_flow_runs_lateness_post;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => FlowRunsService.postFlowRunsLateness({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useFlowRunsServicePostFlowRunsHistory = <TData = Common.FlowRunsServicePostFlowRunsHistoryMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody: Body_flow_run_history_flow_runs_history_post;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody: Body_flow_run_history_flow_runs_history_post;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => FlowRunsService.postFlowRunsHistory({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useFlowRunsServicePostFlowRunsByIdResume = <TData = Common.FlowRunsServicePostFlowRunsByIdResumeMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  id: string;
  requestBody?: Body_resume_flow_run_flow_runs__id__resume_post;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  id: string;
  requestBody?: Body_resume_flow_run_flow_runs__id__resume_post;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ id, requestBody, xPrefectApiVersion }) => FlowRunsService.postFlowRunsByIdResume({ id, requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useFlowRunsServicePostFlowRunsFilter = <TData = Common.FlowRunsServicePostFlowRunsFilterMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody?: Body_read_flow_runs_flow_runs_filter_post;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody?: Body_read_flow_runs_flow_runs_filter_post;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => FlowRunsService.postFlowRunsFilter({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useFlowRunsServicePostFlowRunsByIdSetState = <TData = Common.FlowRunsServicePostFlowRunsByIdSetStateMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  id: string;
  requestBody: Body_set_flow_run_state_flow_runs__id__set_state_post;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  id: string;
  requestBody: Body_set_flow_run_state_flow_runs__id__set_state_post;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ id, requestBody, xPrefectApiVersion }) => FlowRunsService.postFlowRunsByIdSetState({ id, requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useFlowRunsServicePostFlowRunsByIdInput = <TData = Common.FlowRunsServicePostFlowRunsByIdInputMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  id: string;
  requestBody: Body_create_flow_run_input_flow_runs__id__input_post;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  id: string;
  requestBody: Body_create_flow_run_input_flow_runs__id__input_post;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ id, requestBody, xPrefectApiVersion }) => FlowRunsService.postFlowRunsByIdInput({ id, requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useFlowRunsServicePostFlowRunsByIdInputFilter = <TData = Common.FlowRunsServicePostFlowRunsByIdInputFilterMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  id: string;
  requestBody: Body_filter_flow_run_input_flow_runs__id__input_filter_post;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  id: string;
  requestBody: Body_filter_flow_run_input_flow_runs__id__input_filter_post;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ id, requestBody, xPrefectApiVersion }) => FlowRunsService.postFlowRunsByIdInputFilter({ id, requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useFlowRunsServicePostFlowRunsPaginate = <TData = Common.FlowRunsServicePostFlowRunsPaginateMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody?: Body_paginate_flow_runs_flow_runs_paginate_post;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody?: Body_paginate_flow_runs_flow_runs_paginate_post;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => FlowRunsService.postFlowRunsPaginate({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useFlowRunsServicePostUiFlowRunsHistory = <TData = Common.FlowRunsServicePostUiFlowRunsHistoryMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody?: Body_read_flow_run_history_ui_flow_runs_history_post;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody?: Body_read_flow_run_history_ui_flow_runs_history_post;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => FlowRunsService.postUiFlowRunsHistory({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useFlowRunsServicePostUiFlowRunsCountTaskRuns = <TData = Common.FlowRunsServicePostUiFlowRunsCountTaskRunsMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody: Body_count_task_runs_by_flow_run_ui_flow_runs_count_task_runs_post;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody: Body_count_task_runs_by_flow_run_ui_flow_runs_count_task_runs_post;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => FlowRunsService.postUiFlowRunsCountTaskRuns({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useTaskRunsServicePostTaskRuns = <TData = Common.TaskRunsServicePostTaskRunsMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody: TaskRunCreate;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody: TaskRunCreate;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => TaskRunsService.postTaskRuns({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useTaskRunsServicePostTaskRunsCount = <TData = Common.TaskRunsServicePostTaskRunsCountMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody?: Body_count_task_runs_task_runs_count_post;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody?: Body_count_task_runs_task_runs_count_post;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => TaskRunsService.postTaskRunsCount({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useTaskRunsServicePostTaskRunsHistory = <TData = Common.TaskRunsServicePostTaskRunsHistoryMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody: Body_task_run_history_task_runs_history_post;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody: Body_task_run_history_task_runs_history_post;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => TaskRunsService.postTaskRunsHistory({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useTaskRunsServicePostTaskRunsFilter = <TData = Common.TaskRunsServicePostTaskRunsFilterMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody?: Body_read_task_runs_task_runs_filter_post;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody?: Body_read_task_runs_task_runs_filter_post;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => TaskRunsService.postTaskRunsFilter({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useTaskRunsServicePostTaskRunsByIdSetState = <TData = Common.TaskRunsServicePostTaskRunsByIdSetStateMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  id: string;
  requestBody: Body_set_task_run_state_task_runs__id__set_state_post;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  id: string;
  requestBody: Body_set_task_run_state_task_runs__id__set_state_post;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ id, requestBody, xPrefectApiVersion }) => TaskRunsService.postTaskRunsByIdSetState({ id, requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useTaskRunsServicePostUiTaskRunsDashboardCounts = <TData = Common.TaskRunsServicePostUiTaskRunsDashboardCountsMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody: Body_read_dashboard_task_run_counts_ui_task_runs_dashboard_counts_post;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody: Body_read_dashboard_task_run_counts_ui_task_runs_dashboard_counts_post;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => TaskRunsService.postUiTaskRunsDashboardCounts({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useTaskRunsServicePostUiTaskRunsCount = <TData = Common.TaskRunsServicePostUiTaskRunsCountMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody?: Body_read_task_run_counts_by_state_ui_task_runs_count_post;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody?: Body_read_task_run_counts_by_state_ui_task_runs_count_post;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => TaskRunsService.postUiTaskRunsCount({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useFlowRunNotificationPoliciesServicePostFlowRunNotificationPolicies = <TData = Common.FlowRunNotificationPoliciesServicePostFlowRunNotificationPoliciesMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody: FlowRunNotificationPolicyCreate;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody: FlowRunNotificationPolicyCreate;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => FlowRunNotificationPoliciesService.postFlowRunNotificationPolicies({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useFlowRunNotificationPoliciesServicePostFlowRunNotificationPoliciesFilter = <TData = Common.FlowRunNotificationPoliciesServicePostFlowRunNotificationPoliciesFilterMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody?: Body_read_flow_run_notification_policies_flow_run_notification_policies_filter_post;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody?: Body_read_flow_run_notification_policies_flow_run_notification_policies_filter_post;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => FlowRunNotificationPoliciesService.postFlowRunNotificationPoliciesFilter({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useDeploymentsServicePostDeployments = <TData = Common.DeploymentsServicePostDeploymentsMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody: DeploymentCreate;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody: DeploymentCreate;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => DeploymentsService.postDeployments({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useDeploymentsServicePostDeploymentsFilter = <TData = Common.DeploymentsServicePostDeploymentsFilterMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody?: Body_read_deployments_deployments_filter_post;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody?: Body_read_deployments_deployments_filter_post;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => DeploymentsService.postDeploymentsFilter({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useDeploymentsServicePostDeploymentsPaginate = <TData = Common.DeploymentsServicePostDeploymentsPaginateMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody?: Body_paginate_deployments_deployments_paginate_post;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody?: Body_paginate_deployments_deployments_paginate_post;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => DeploymentsService.postDeploymentsPaginate({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useDeploymentsServicePostDeploymentsGetScheduledFlowRuns = <TData = Common.DeploymentsServicePostDeploymentsGetScheduledFlowRunsMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody: Body_get_scheduled_flow_runs_for_deployments_deployments_get_scheduled_flow_runs_post;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody: Body_get_scheduled_flow_runs_for_deployments_deployments_get_scheduled_flow_runs_post;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => DeploymentsService.postDeploymentsGetScheduledFlowRuns({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useDeploymentsServicePostDeploymentsCount = <TData = Common.DeploymentsServicePostDeploymentsCountMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody?: Body_count_deployments_deployments_count_post;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody?: Body_count_deployments_deployments_count_post;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => DeploymentsService.postDeploymentsCount({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useDeploymentsServicePostDeploymentsByIdSchedule = <TData = Common.DeploymentsServicePostDeploymentsByIdScheduleMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  id: string;
  requestBody?: Body_schedule_deployment_deployments__id__schedule_post;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  id: string;
  requestBody?: Body_schedule_deployment_deployments__id__schedule_post;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ id, requestBody, xPrefectApiVersion }) => DeploymentsService.postDeploymentsByIdSchedule({ id, requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useDeploymentsServicePostDeploymentsByIdResumeDeployment = <TData = Common.DeploymentsServicePostDeploymentsByIdResumeDeploymentMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  id: string;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  id: string;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ id, xPrefectApiVersion }) => DeploymentsService.postDeploymentsByIdResumeDeployment({ id, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useDeploymentsServicePostDeploymentsByIdPauseDeployment = <TData = Common.DeploymentsServicePostDeploymentsByIdPauseDeploymentMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  id: string;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  id: string;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ id, xPrefectApiVersion }) => DeploymentsService.postDeploymentsByIdPauseDeployment({ id, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useDeploymentsServicePostDeploymentsByIdCreateFlowRun = <TData = Common.DeploymentsServicePostDeploymentsByIdCreateFlowRunMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  id: string;
  requestBody: DeploymentFlowRunCreate;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  id: string;
  requestBody: DeploymentFlowRunCreate;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ id, requestBody, xPrefectApiVersion }) => DeploymentsService.postDeploymentsByIdCreateFlowRun({ id, requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useDeploymentsServicePostDeploymentsByIdSchedules = <TData = Common.DeploymentsServicePostDeploymentsByIdSchedulesMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  id: string;
  requestBody: DeploymentScheduleCreate[];
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  id: string;
  requestBody: DeploymentScheduleCreate[];
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ id, requestBody, xPrefectApiVersion }) => DeploymentsService.postDeploymentsByIdSchedules({ id, requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useSavedSearchesServicePostSavedSearchesFilter = <TData = Common.SavedSearchesServicePostSavedSearchesFilterMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody?: Body_read_saved_searches_saved_searches_filter_post;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody?: Body_read_saved_searches_saved_searches_filter_post;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => SavedSearchesService.postSavedSearchesFilter({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useLogsServicePostLogs = <TData = Common.LogsServicePostLogsMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody: LogCreate[];
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody: LogCreate[];
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => LogsService.postLogs({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useLogsServicePostLogsFilter = <TData = Common.LogsServicePostLogsFilterMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody?: Body_read_logs_logs_filter_post;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody?: Body_read_logs_logs_filter_post;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => LogsService.postLogsFilter({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useConcurrencyLimitsServicePostConcurrencyLimits = <TData = Common.ConcurrencyLimitsServicePostConcurrencyLimitsMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody: ConcurrencyLimitCreate;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody: ConcurrencyLimitCreate;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => ConcurrencyLimitsService.postConcurrencyLimits({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useConcurrencyLimitsServicePostConcurrencyLimitsFilter = <TData = Common.ConcurrencyLimitsServicePostConcurrencyLimitsFilterMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody?: Body_read_concurrency_limits_concurrency_limits_filter_post;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody?: Body_read_concurrency_limits_concurrency_limits_filter_post;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => ConcurrencyLimitsService.postConcurrencyLimitsFilter({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useConcurrencyLimitsServicePostConcurrencyLimitsTagByTagReset = <TData = Common.ConcurrencyLimitsServicePostConcurrencyLimitsTagByTagResetMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody?: Body_reset_concurrency_limit_by_tag_concurrency_limits_tag__tag__reset_post;
  tag: string;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody?: Body_reset_concurrency_limit_by_tag_concurrency_limits_tag__tag__reset_post;
  tag: string;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, tag, xPrefectApiVersion }) => ConcurrencyLimitsService.postConcurrencyLimitsTagByTagReset({ requestBody, tag, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useConcurrencyLimitsServicePostConcurrencyLimitsIncrement = <TData = Common.ConcurrencyLimitsServicePostConcurrencyLimitsIncrementMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody: Body_increment_concurrency_limits_v1_concurrency_limits_increment_post;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody: Body_increment_concurrency_limits_v1_concurrency_limits_increment_post;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => ConcurrencyLimitsService.postConcurrencyLimitsIncrement({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useConcurrencyLimitsServicePostConcurrencyLimitsDecrement = <TData = Common.ConcurrencyLimitsServicePostConcurrencyLimitsDecrementMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody: Body_decrement_concurrency_limits_v1_concurrency_limits_decrement_post;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody: Body_decrement_concurrency_limits_v1_concurrency_limits_decrement_post;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => ConcurrencyLimitsService.postConcurrencyLimitsDecrement({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useConcurrencyLimitsV2ServicePostV2ConcurrencyLimits = <TData = Common.ConcurrencyLimitsV2ServicePostV2ConcurrencyLimitsMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody: ConcurrencyLimitV2Create;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody: ConcurrencyLimitV2Create;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => ConcurrencyLimitsV2Service.postV2ConcurrencyLimits({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useConcurrencyLimitsV2ServicePostV2ConcurrencyLimitsFilter = <TData = Common.ConcurrencyLimitsV2ServicePostV2ConcurrencyLimitsFilterMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody?: Body_read_all_concurrency_limits_v2_v2_concurrency_limits_filter_post;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody?: Body_read_all_concurrency_limits_v2_v2_concurrency_limits_filter_post;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => ConcurrencyLimitsV2Service.postV2ConcurrencyLimitsFilter({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useConcurrencyLimitsV2ServicePostV2ConcurrencyLimitsIncrement = <TData = Common.ConcurrencyLimitsV2ServicePostV2ConcurrencyLimitsIncrementMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody: Body_bulk_increment_active_slots_v2_concurrency_limits_increment_post;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody: Body_bulk_increment_active_slots_v2_concurrency_limits_increment_post;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => ConcurrencyLimitsV2Service.postV2ConcurrencyLimitsIncrement({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useConcurrencyLimitsV2ServicePostV2ConcurrencyLimitsDecrement = <TData = Common.ConcurrencyLimitsV2ServicePostV2ConcurrencyLimitsDecrementMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody: Body_bulk_decrement_active_slots_v2_concurrency_limits_decrement_post;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody: Body_bulk_decrement_active_slots_v2_concurrency_limits_decrement_post;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => ConcurrencyLimitsV2Service.postV2ConcurrencyLimitsDecrement({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useBlockTypesServicePostBlockTypes = <TData = Common.BlockTypesServicePostBlockTypesMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody: BlockTypeCreate;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody: BlockTypeCreate;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => BlockTypesService.postBlockTypes({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useBlockTypesServicePostBlockTypesFilter = <TData = Common.BlockTypesServicePostBlockTypesFilterMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody?: Body_read_block_types_block_types_filter_post;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody?: Body_read_block_types_block_types_filter_post;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => BlockTypesService.postBlockTypesFilter({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useBlockTypesServicePostBlockTypesInstallSystemBlockTypes = <TData = Common.BlockTypesServicePostBlockTypesInstallSystemBlockTypesMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ xPrefectApiVersion }) => BlockTypesService.postBlockTypesInstallSystemBlockTypes({ xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useBlockDocumentsServicePostBlockDocuments = <TData = Common.BlockDocumentsServicePostBlockDocumentsMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody: BlockDocumentCreate;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody: BlockDocumentCreate;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => BlockDocumentsService.postBlockDocuments({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useBlockDocumentsServicePostBlockDocumentsFilter = <TData = Common.BlockDocumentsServicePostBlockDocumentsFilterMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody?: Body_read_block_documents_block_documents_filter_post;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody?: Body_read_block_documents_block_documents_filter_post;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => BlockDocumentsService.postBlockDocumentsFilter({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useBlockDocumentsServicePostBlockDocumentsCount = <TData = Common.BlockDocumentsServicePostBlockDocumentsCountMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody?: Body_count_block_documents_block_documents_count_post;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody?: Body_count_block_documents_block_documents_count_post;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => BlockDocumentsService.postBlockDocumentsCount({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useWorkPoolsServicePostWorkPools = <TData = Common.WorkPoolsServicePostWorkPoolsMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody: WorkPoolCreate;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody: WorkPoolCreate;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => WorkPoolsService.postWorkPools({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useWorkPoolsServicePostWorkPoolsFilter = <TData = Common.WorkPoolsServicePostWorkPoolsFilterMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody?: Body_read_work_pools_work_pools_filter_post;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody?: Body_read_work_pools_work_pools_filter_post;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => WorkPoolsService.postWorkPoolsFilter({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useWorkPoolsServicePostWorkPoolsCount = <TData = Common.WorkPoolsServicePostWorkPoolsCountMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody?: Body_count_work_pools_work_pools_count_post;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody?: Body_count_work_pools_work_pools_count_post;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => WorkPoolsService.postWorkPoolsCount({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useWorkPoolsServicePostWorkPoolsByNameGetScheduledFlowRuns = <TData = Common.WorkPoolsServicePostWorkPoolsByNameGetScheduledFlowRunsMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  name: string;
  requestBody?: Body_get_scheduled_flow_runs_work_pools__name__get_scheduled_flow_runs_post;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  name: string;
  requestBody?: Body_get_scheduled_flow_runs_work_pools__name__get_scheduled_flow_runs_post;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ name, requestBody, xPrefectApiVersion }) => WorkPoolsService.postWorkPoolsByNameGetScheduledFlowRuns({ name, requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useWorkPoolsServicePostWorkPoolsByWorkPoolNameQueues = <TData = Common.WorkPoolsServicePostWorkPoolsByWorkPoolNameQueuesMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody: WorkQueueCreate;
  workPoolName: string;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody: WorkQueueCreate;
  workPoolName: string;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, workPoolName, xPrefectApiVersion }) => WorkPoolsService.postWorkPoolsByWorkPoolNameQueues({ requestBody, workPoolName, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useWorkPoolsServicePostWorkPoolsByWorkPoolNameQueuesFilter = <TData = Common.WorkPoolsServicePostWorkPoolsByWorkPoolNameQueuesFilterMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody?: Body_read_work_queues_work_pools__work_pool_name__queues_filter_post;
  workPoolName: string;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody?: Body_read_work_queues_work_pools__work_pool_name__queues_filter_post;
  workPoolName: string;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, workPoolName, xPrefectApiVersion }) => WorkPoolsService.postWorkPoolsByWorkPoolNameQueuesFilter({ requestBody, workPoolName, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useWorkPoolsServicePostWorkPoolsByWorkPoolNameWorkersHeartbeat = <TData = Common.WorkPoolsServicePostWorkPoolsByWorkPoolNameWorkersHeartbeatMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody: Body_worker_heartbeat_work_pools__work_pool_name__workers_heartbeat_post;
  workPoolName: string;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody: Body_worker_heartbeat_work_pools__work_pool_name__workers_heartbeat_post;
  workPoolName: string;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, workPoolName, xPrefectApiVersion }) => WorkPoolsService.postWorkPoolsByWorkPoolNameWorkersHeartbeat({ requestBody, workPoolName, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useWorkPoolsServicePostWorkPoolsByWorkPoolNameWorkersFilter = <TData = Common.WorkPoolsServicePostWorkPoolsByWorkPoolNameWorkersFilterMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody?: Body_read_workers_work_pools__work_pool_name__workers_filter_post;
  workPoolName: string;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody?: Body_read_workers_work_pools__work_pool_name__workers_filter_post;
  workPoolName: string;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, workPoolName, xPrefectApiVersion }) => WorkPoolsService.postWorkPoolsByWorkPoolNameWorkersFilter({ requestBody, workPoolName, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useTaskWorkersServicePostTaskWorkersFilter = <TData = Common.TaskWorkersServicePostTaskWorkersFilterMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody?: Body_read_task_workers_task_workers_filter_post;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody?: Body_read_task_workers_task_workers_filter_post;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => TaskWorkersService.postTaskWorkersFilter({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useWorkQueuesServicePostWorkQueues = <TData = Common.WorkQueuesServicePostWorkQueuesMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody: WorkQueueCreate;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody: WorkQueueCreate;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => WorkQueuesService.postWorkQueues({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useWorkQueuesServicePostWorkQueuesByIdGetRuns = <TData = Common.WorkQueuesServicePostWorkQueuesByIdGetRunsMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  id: string;
  requestBody?: Body_read_work_queue_runs_work_queues__id__get_runs_post;
  xPrefectApiVersion?: string;
  xPrefectUi?: boolean;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  id: string;
  requestBody?: Body_read_work_queue_runs_work_queues__id__get_runs_post;
  xPrefectApiVersion?: string;
  xPrefectUi?: boolean;
}, TContext>({ mutationFn: ({ id, requestBody, xPrefectApiVersion, xPrefectUi }) => WorkQueuesService.postWorkQueuesByIdGetRuns({ id, requestBody, xPrefectApiVersion, xPrefectUi }) as unknown as Promise<TData>, ...options });
export const useWorkQueuesServicePostWorkQueuesFilter = <TData = Common.WorkQueuesServicePostWorkQueuesFilterMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody?: Body_read_work_queues_work_queues_filter_post;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody?: Body_read_work_queues_work_queues_filter_post;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => WorkQueuesService.postWorkQueuesFilter({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useArtifactsServicePostArtifacts = <TData = Common.ArtifactsServicePostArtifactsMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody: ArtifactCreate;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody: ArtifactCreate;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => ArtifactsService.postArtifacts({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useArtifactsServicePostArtifactsFilter = <TData = Common.ArtifactsServicePostArtifactsFilterMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody?: Body_read_artifacts_artifacts_filter_post;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody?: Body_read_artifacts_artifacts_filter_post;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => ArtifactsService.postArtifactsFilter({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useArtifactsServicePostArtifactsLatestFilter = <TData = Common.ArtifactsServicePostArtifactsLatestFilterMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody?: Body_read_latest_artifacts_artifacts_latest_filter_post;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody?: Body_read_latest_artifacts_artifacts_latest_filter_post;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => ArtifactsService.postArtifactsLatestFilter({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useArtifactsServicePostArtifactsCount = <TData = Common.ArtifactsServicePostArtifactsCountMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody?: Body_count_artifacts_artifacts_count_post;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody?: Body_count_artifacts_artifacts_count_post;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => ArtifactsService.postArtifactsCount({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useArtifactsServicePostArtifactsLatestCount = <TData = Common.ArtifactsServicePostArtifactsLatestCountMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody?: Body_count_latest_artifacts_artifacts_latest_count_post;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody?: Body_count_latest_artifacts_artifacts_latest_count_post;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => ArtifactsService.postArtifactsLatestCount({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useBlockSchemasServicePostBlockSchemas = <TData = Common.BlockSchemasServicePostBlockSchemasMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody: BlockSchemaCreate;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody: BlockSchemaCreate;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => BlockSchemasService.postBlockSchemas({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useBlockSchemasServicePostBlockSchemasFilter = <TData = Common.BlockSchemasServicePostBlockSchemasFilterMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody?: Body_read_block_schemas_block_schemas_filter_post;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody?: Body_read_block_schemas_block_schemas_filter_post;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => BlockSchemasService.postBlockSchemasFilter({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useVariablesServicePostVariables = <TData = Common.VariablesServicePostVariablesMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody: VariableCreate;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody: VariableCreate;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => VariablesService.postVariables({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useVariablesServicePostVariablesFilter = <TData = Common.VariablesServicePostVariablesFilterMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody?: Body_read_variables_variables_filter_post;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody?: Body_read_variables_variables_filter_post;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => VariablesService.postVariablesFilter({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useVariablesServicePostVariablesCount = <TData = Common.VariablesServicePostVariablesCountMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody?: Body_count_variables_variables_count_post;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody?: Body_count_variables_variables_count_post;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => VariablesService.postVariablesCount({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useEventsServicePostEvents = <TData = Common.EventsServicePostEventsMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody: Event[];
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody: Event[];
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => EventsService.postEvents({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useEventsServicePostEventsFilter = <TData = Common.EventsServicePostEventsFilterMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody?: Body_read_events_events_filter_post;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody?: Body_read_events_events_filter_post;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => EventsService.postEventsFilter({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useEventsServicePostEventsCountByByCountable = <TData = Common.EventsServicePostEventsCountByByCountableMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  countable: Countable;
  requestBody: Body_count_account_events_events_count_by__countable__post;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  countable: Countable;
  requestBody: Body_count_account_events_events_count_by__countable__post;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ countable, requestBody, xPrefectApiVersion }) => EventsService.postEventsCountByByCountable({ countable, requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useAutomationsServicePostAutomations = <TData = Common.AutomationsServicePostAutomationsMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody: AutomationCreate;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody: AutomationCreate;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => AutomationsService.postAutomations({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useAutomationsServicePostAutomationsFilter = <TData = Common.AutomationsServicePostAutomationsFilterMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody?: Body_read_automations_automations_filter_post;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody?: Body_read_automations_automations_filter_post;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => AutomationsService.postAutomationsFilter({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useAutomationsServicePostAutomationsCount = <TData = Common.AutomationsServicePostAutomationsCountMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ xPrefectApiVersion }) => AutomationsService.postAutomationsCount({ xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useAutomationsServicePostTemplatesValidate = <TData = Common.AutomationsServicePostTemplatesValidateMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody?: string;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody?: string;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => AutomationsService.postTemplatesValidate({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useUiServicePostUiFlowsCountDeployments = <TData = Common.UiServicePostUiFlowsCountDeploymentsMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody: Body_count_deployments_by_flow_ui_flows_count_deployments_post;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody: Body_count_deployments_by_flow_ui_flows_count_deployments_post;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => UiService.postUiFlowsCountDeployments({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useUiServicePostUiFlowsNextRuns = <TData = Common.UiServicePostUiFlowsNextRunsMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody: Body_next_runs_by_flow_ui_flows_next_runs_post;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody: Body_next_runs_by_flow_ui_flows_next_runs_post;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => UiService.postUiFlowsNextRuns({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useUiServicePostUiFlowRunsHistory = <TData = Common.UiServicePostUiFlowRunsHistoryMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody?: Body_read_flow_run_history_ui_flow_runs_history_post;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody?: Body_read_flow_run_history_ui_flow_runs_history_post;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => UiService.postUiFlowRunsHistory({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useUiServicePostUiFlowRunsCountTaskRuns = <TData = Common.UiServicePostUiFlowRunsCountTaskRunsMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody: Body_count_task_runs_by_flow_run_ui_flow_runs_count_task_runs_post;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody: Body_count_task_runs_by_flow_run_ui_flow_runs_count_task_runs_post;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => UiService.postUiFlowRunsCountTaskRuns({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useUiServicePostUiSchemasValidate = <TData = Common.UiServicePostUiSchemasValidateMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody: Body_validate_obj_ui_schemas_validate_post;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody: Body_validate_obj_ui_schemas_validate_post;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => UiService.postUiSchemasValidate({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useUiServicePostUiTaskRunsDashboardCounts = <TData = Common.UiServicePostUiTaskRunsDashboardCountsMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody: Body_read_dashboard_task_run_counts_ui_task_runs_dashboard_counts_post;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody: Body_read_dashboard_task_run_counts_ui_task_runs_dashboard_counts_post;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => UiService.postUiTaskRunsDashboardCounts({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useUiServicePostUiTaskRunsCount = <TData = Common.UiServicePostUiTaskRunsCountMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody?: Body_read_task_run_counts_by_state_ui_task_runs_count_post;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody?: Body_read_task_run_counts_by_state_ui_task_runs_count_post;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => UiService.postUiTaskRunsCount({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useSchemasServicePostUiSchemasValidate = <TData = Common.SchemasServicePostUiSchemasValidateMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody: Body_validate_obj_ui_schemas_validate_post;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody: Body_validate_obj_ui_schemas_validate_post;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => SchemasService.postUiSchemasValidate({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useAdminServicePostAdminDatabaseClear = <TData = Common.AdminServicePostAdminDatabaseClearMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody?: Body_clear_database_admin_database_clear_post;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody?: Body_clear_database_admin_database_clear_post;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => AdminService.postAdminDatabaseClear({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useAdminServicePostAdminDatabaseDrop = <TData = Common.AdminServicePostAdminDatabaseDropMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody?: Body_drop_database_admin_database_drop_post;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody?: Body_drop_database_admin_database_drop_post;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => AdminService.postAdminDatabaseDrop({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useAdminServicePostAdminDatabaseCreate = <TData = Common.AdminServicePostAdminDatabaseCreateMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody?: Body_create_database_admin_database_create_post;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody?: Body_create_database_admin_database_create_post;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => AdminService.postAdminDatabaseCreate({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useSavedSearchesServicePutSavedSearches = <TData = Common.SavedSearchesServicePutSavedSearchesMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  requestBody: SavedSearchCreate;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  requestBody: SavedSearchCreate;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ requestBody, xPrefectApiVersion }) => SavedSearchesService.putSavedSearches({ requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useAutomationsServicePutAutomationsById = <TData = Common.AutomationsServicePutAutomationsByIdMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  id: string;
  requestBody: AutomationUpdate;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  id: string;
  requestBody: AutomationUpdate;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ id, requestBody, xPrefectApiVersion }) => AutomationsService.putAutomationsById({ id, requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useFlowsServicePatchFlowsById = <TData = Common.FlowsServicePatchFlowsByIdMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  id: string;
  requestBody: FlowUpdate;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  id: string;
  requestBody: FlowUpdate;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ id, requestBody, xPrefectApiVersion }) => FlowsService.patchFlowsById({ id, requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useFlowRunsServicePatchFlowRunsById = <TData = Common.FlowRunsServicePatchFlowRunsByIdMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  id: string;
  requestBody: FlowRunUpdate;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  id: string;
  requestBody: FlowRunUpdate;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ id, requestBody, xPrefectApiVersion }) => FlowRunsService.patchFlowRunsById({ id, requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useFlowRunsServicePatchFlowRunsByIdLabels = <TData = Common.FlowRunsServicePatchFlowRunsByIdLabelsMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  id: string;
  requestBody: { [key: string]: unknown; };
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  id: string;
  requestBody: { [key: string]: unknown; };
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ id, requestBody, xPrefectApiVersion }) => FlowRunsService.patchFlowRunsByIdLabels({ id, requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useTaskRunsServicePatchTaskRunsById = <TData = Common.TaskRunsServicePatchTaskRunsByIdMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  id: string;
  requestBody: TaskRunUpdate;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  id: string;
  requestBody: TaskRunUpdate;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ id, requestBody, xPrefectApiVersion }) => TaskRunsService.patchTaskRunsById({ id, requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useFlowRunNotificationPoliciesServicePatchFlowRunNotificationPoliciesById = <TData = Common.FlowRunNotificationPoliciesServicePatchFlowRunNotificationPoliciesByIdMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  id: string;
  requestBody: FlowRunNotificationPolicyUpdate;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  id: string;
  requestBody: FlowRunNotificationPolicyUpdate;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ id, requestBody, xPrefectApiVersion }) => FlowRunNotificationPoliciesService.patchFlowRunNotificationPoliciesById({ id, requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useDeploymentsServicePatchDeploymentsById = <TData = Common.DeploymentsServicePatchDeploymentsByIdMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  id: string;
  requestBody: DeploymentUpdate;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  id: string;
  requestBody: DeploymentUpdate;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ id, requestBody, xPrefectApiVersion }) => DeploymentsService.patchDeploymentsById({ id, requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useDeploymentsServicePatchDeploymentsByIdSchedulesByScheduleId = <TData = Common.DeploymentsServicePatchDeploymentsByIdSchedulesByScheduleIdMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  id: string;
  requestBody: DeploymentScheduleUpdate;
  scheduleId: string;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  id: string;
  requestBody: DeploymentScheduleUpdate;
  scheduleId: string;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ id, requestBody, scheduleId, xPrefectApiVersion }) => DeploymentsService.patchDeploymentsByIdSchedulesByScheduleId({ id, requestBody, scheduleId, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useConcurrencyLimitsV2ServicePatchV2ConcurrencyLimitsByIdOrName = <TData = Common.ConcurrencyLimitsV2ServicePatchV2ConcurrencyLimitsByIdOrNameMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  idOrName: string;
  requestBody: ConcurrencyLimitV2Update;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  idOrName: string;
  requestBody: ConcurrencyLimitV2Update;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ idOrName, requestBody, xPrefectApiVersion }) => ConcurrencyLimitsV2Service.patchV2ConcurrencyLimitsByIdOrName({ idOrName, requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useBlockTypesServicePatchBlockTypesById = <TData = Common.BlockTypesServicePatchBlockTypesByIdMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  id: string;
  requestBody: BlockTypeUpdate;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  id: string;
  requestBody: BlockTypeUpdate;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ id, requestBody, xPrefectApiVersion }) => BlockTypesService.patchBlockTypesById({ id, requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useBlockDocumentsServicePatchBlockDocumentsById = <TData = Common.BlockDocumentsServicePatchBlockDocumentsByIdMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  id: string;
  requestBody: BlockDocumentUpdate;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  id: string;
  requestBody: BlockDocumentUpdate;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ id, requestBody, xPrefectApiVersion }) => BlockDocumentsService.patchBlockDocumentsById({ id, requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useWorkPoolsServicePatchWorkPoolsByName = <TData = Common.WorkPoolsServicePatchWorkPoolsByNameMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  name: string;
  requestBody: WorkPoolUpdate;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  name: string;
  requestBody: WorkPoolUpdate;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ name, requestBody, xPrefectApiVersion }) => WorkPoolsService.patchWorkPoolsByName({ name, requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useWorkPoolsServicePatchWorkPoolsByWorkPoolNameQueuesByName = <TData = Common.WorkPoolsServicePatchWorkPoolsByWorkPoolNameQueuesByNameMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  name: string;
  requestBody: WorkQueueUpdate;
  workPoolName: string;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  name: string;
  requestBody: WorkQueueUpdate;
  workPoolName: string;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ name, requestBody, workPoolName, xPrefectApiVersion }) => WorkPoolsService.patchWorkPoolsByWorkPoolNameQueuesByName({ name, requestBody, workPoolName, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useWorkQueuesServicePatchWorkQueuesById = <TData = Common.WorkQueuesServicePatchWorkQueuesByIdMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  id: string;
  requestBody: WorkQueueUpdate;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  id: string;
  requestBody: WorkQueueUpdate;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ id, requestBody, xPrefectApiVersion }) => WorkQueuesService.patchWorkQueuesById({ id, requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useArtifactsServicePatchArtifactsById = <TData = Common.ArtifactsServicePatchArtifactsByIdMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  id: string;
  requestBody: ArtifactUpdate;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  id: string;
  requestBody: ArtifactUpdate;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ id, requestBody, xPrefectApiVersion }) => ArtifactsService.patchArtifactsById({ id, requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useVariablesServicePatchVariablesById = <TData = Common.VariablesServicePatchVariablesByIdMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  id: string;
  requestBody: VariableUpdate;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  id: string;
  requestBody: VariableUpdate;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ id, requestBody, xPrefectApiVersion }) => VariablesService.patchVariablesById({ id, requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useVariablesServicePatchVariablesNameByName = <TData = Common.VariablesServicePatchVariablesNameByNameMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  name: string;
  requestBody: VariableUpdate;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  name: string;
  requestBody: VariableUpdate;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ name, requestBody, xPrefectApiVersion }) => VariablesService.patchVariablesNameByName({ name, requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useAutomationsServicePatchAutomationsById = <TData = Common.AutomationsServicePatchAutomationsByIdMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  id: string;
  requestBody: AutomationPartialUpdate;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  id: string;
  requestBody: AutomationPartialUpdate;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ id, requestBody, xPrefectApiVersion }) => AutomationsService.patchAutomationsById({ id, requestBody, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useFlowsServiceDeleteFlowsById = <TData = Common.FlowsServiceDeleteFlowsByIdMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  id: string;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  id: string;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ id, xPrefectApiVersion }) => FlowsService.deleteFlowsById({ id, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useFlowRunsServiceDeleteFlowRunsById = <TData = Common.FlowRunsServiceDeleteFlowRunsByIdMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  id: string;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  id: string;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ id, xPrefectApiVersion }) => FlowRunsService.deleteFlowRunsById({ id, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useFlowRunsServiceDeleteFlowRunsByIdInputByKey = <TData = Common.FlowRunsServiceDeleteFlowRunsByIdInputByKeyMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  id: string;
  key: string;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  id: string;
  key: string;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ id, key, xPrefectApiVersion }) => FlowRunsService.deleteFlowRunsByIdInputByKey({ id, key, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useTaskRunsServiceDeleteTaskRunsById = <TData = Common.TaskRunsServiceDeleteTaskRunsByIdMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  id: string;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  id: string;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ id, xPrefectApiVersion }) => TaskRunsService.deleteTaskRunsById({ id, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useFlowRunNotificationPoliciesServiceDeleteFlowRunNotificationPoliciesById = <TData = Common.FlowRunNotificationPoliciesServiceDeleteFlowRunNotificationPoliciesByIdMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  id: string;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  id: string;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ id, xPrefectApiVersion }) => FlowRunNotificationPoliciesService.deleteFlowRunNotificationPoliciesById({ id, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useDeploymentsServiceDeleteDeploymentsById = <TData = Common.DeploymentsServiceDeleteDeploymentsByIdMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  id: string;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  id: string;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ id, xPrefectApiVersion }) => DeploymentsService.deleteDeploymentsById({ id, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useDeploymentsServiceDeleteDeploymentsByIdSchedulesByScheduleId = <TData = Common.DeploymentsServiceDeleteDeploymentsByIdSchedulesByScheduleIdMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  id: string;
  scheduleId: string;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  id: string;
  scheduleId: string;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ id, scheduleId, xPrefectApiVersion }) => DeploymentsService.deleteDeploymentsByIdSchedulesByScheduleId({ id, scheduleId, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useSavedSearchesServiceDeleteSavedSearchesById = <TData = Common.SavedSearchesServiceDeleteSavedSearchesByIdMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  id: string;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  id: string;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ id, xPrefectApiVersion }) => SavedSearchesService.deleteSavedSearchesById({ id, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useConcurrencyLimitsServiceDeleteConcurrencyLimitsById = <TData = Common.ConcurrencyLimitsServiceDeleteConcurrencyLimitsByIdMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  id: string;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  id: string;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ id, xPrefectApiVersion }) => ConcurrencyLimitsService.deleteConcurrencyLimitsById({ id, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useConcurrencyLimitsServiceDeleteConcurrencyLimitsTagByTag = <TData = Common.ConcurrencyLimitsServiceDeleteConcurrencyLimitsTagByTagMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  tag: string;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  tag: string;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ tag, xPrefectApiVersion }) => ConcurrencyLimitsService.deleteConcurrencyLimitsTagByTag({ tag, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useConcurrencyLimitsV2ServiceDeleteV2ConcurrencyLimitsByIdOrName = <TData = Common.ConcurrencyLimitsV2ServiceDeleteV2ConcurrencyLimitsByIdOrNameMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  idOrName: string;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  idOrName: string;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ idOrName, xPrefectApiVersion }) => ConcurrencyLimitsV2Service.deleteV2ConcurrencyLimitsByIdOrName({ idOrName, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useBlockTypesServiceDeleteBlockTypesById = <TData = Common.BlockTypesServiceDeleteBlockTypesByIdMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  id: string;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  id: string;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ id, xPrefectApiVersion }) => BlockTypesService.deleteBlockTypesById({ id, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useBlockDocumentsServiceDeleteBlockDocumentsById = <TData = Common.BlockDocumentsServiceDeleteBlockDocumentsByIdMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  id: string;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  id: string;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ id, xPrefectApiVersion }) => BlockDocumentsService.deleteBlockDocumentsById({ id, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useWorkPoolsServiceDeleteWorkPoolsByName = <TData = Common.WorkPoolsServiceDeleteWorkPoolsByNameMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  name: string;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  name: string;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ name, xPrefectApiVersion }) => WorkPoolsService.deleteWorkPoolsByName({ name, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useWorkPoolsServiceDeleteWorkPoolsByWorkPoolNameQueuesByName = <TData = Common.WorkPoolsServiceDeleteWorkPoolsByWorkPoolNameQueuesByNameMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  name: string;
  workPoolName: string;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  name: string;
  workPoolName: string;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ name, workPoolName, xPrefectApiVersion }) => WorkPoolsService.deleteWorkPoolsByWorkPoolNameQueuesByName({ name, workPoolName, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useWorkPoolsServiceDeleteWorkPoolsByWorkPoolNameWorkersByName = <TData = Common.WorkPoolsServiceDeleteWorkPoolsByWorkPoolNameWorkersByNameMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  name: string;
  workPoolName: string;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  name: string;
  workPoolName: string;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ name, workPoolName, xPrefectApiVersion }) => WorkPoolsService.deleteWorkPoolsByWorkPoolNameWorkersByName({ name, workPoolName, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useWorkQueuesServiceDeleteWorkQueuesById = <TData = Common.WorkQueuesServiceDeleteWorkQueuesByIdMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  id: string;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  id: string;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ id, xPrefectApiVersion }) => WorkQueuesService.deleteWorkQueuesById({ id, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useArtifactsServiceDeleteArtifactsById = <TData = Common.ArtifactsServiceDeleteArtifactsByIdMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  id: string;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  id: string;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ id, xPrefectApiVersion }) => ArtifactsService.deleteArtifactsById({ id, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useBlockSchemasServiceDeleteBlockSchemasById = <TData = Common.BlockSchemasServiceDeleteBlockSchemasByIdMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  id: string;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  id: string;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ id, xPrefectApiVersion }) => BlockSchemasService.deleteBlockSchemasById({ id, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useVariablesServiceDeleteVariablesById = <TData = Common.VariablesServiceDeleteVariablesByIdMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  id: string;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  id: string;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ id, xPrefectApiVersion }) => VariablesService.deleteVariablesById({ id, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useVariablesServiceDeleteVariablesNameByName = <TData = Common.VariablesServiceDeleteVariablesNameByNameMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  name: string;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  name: string;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ name, xPrefectApiVersion }) => VariablesService.deleteVariablesNameByName({ name, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useAutomationsServiceDeleteAutomationsById = <TData = Common.AutomationsServiceDeleteAutomationsByIdMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  id: string;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  id: string;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ id, xPrefectApiVersion }) => AutomationsService.deleteAutomationsById({ id, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
export const useAutomationsServiceDeleteAutomationsOwnedByByResourceId = <TData = Common.AutomationsServiceDeleteAutomationsOwnedByByResourceIdMutationResult, TError = unknown, TContext = unknown>(options?: Omit<UseMutationOptions<TData, TError, {
  resourceId: string;
  xPrefectApiVersion?: string;
}, TContext>, "mutationFn">) => useMutation<TData, TError, {
  resourceId: string;
  xPrefectApiVersion?: string;
}, TContext>({ mutationFn: ({ resourceId, xPrefectApiVersion }) => AutomationsService.deleteAutomationsOwnedByByResourceId({ resourceId, xPrefectApiVersion }) as unknown as Promise<TData>, ...options });
