// generated with @7nohe/openapi-react-query-codegen@1.6.2 

import { UseQueryResult } from "@tanstack/react-query";
import { AdminService, ArtifactsService, AutomationsService, BlockCapabilitiesService, BlockDocumentsService, BlockSchemasService, BlockTypesService, CollectionsService, ConcurrencyLimitsService, ConcurrencyLimitsV2Service, DefaultService, DeploymentsService, EventsService, FlowRunNotificationPoliciesService, FlowRunStatesService, FlowRunsService, FlowsService, LogsService, RootService, SavedSearchesService, SchemasService, TaskRunStatesService, TaskRunsService, TaskWorkersService, UiService, VariablesService, WorkPoolsService, WorkQueuesService } from "../requests/services.gen";
export type RootServiceGetHealthDefaultResponse = Awaited<ReturnType<typeof RootService.getHealth>>;
export type RootServiceGetHealthQueryResult<TData = RootServiceGetHealthDefaultResponse, TError = unknown> = UseQueryResult<TData, TError>;
export const useRootServiceGetHealthKey = "RootServiceGetHealth";
export const UseRootServiceGetHealthKeyFn = (queryKey?: Array<unknown>) => [useRootServiceGetHealthKey, ...(queryKey ?? [])];
export type RootServiceGetVersionDefaultResponse = Awaited<ReturnType<typeof RootService.getVersion>>;
export type RootServiceGetVersionQueryResult<TData = RootServiceGetVersionDefaultResponse, TError = unknown> = UseQueryResult<TData, TError>;
export const useRootServiceGetVersionKey = "RootServiceGetVersion";
export const UseRootServiceGetVersionKeyFn = (queryKey?: Array<unknown>) => [useRootServiceGetVersionKey, ...(queryKey ?? [])];
export type RootServiceGetHelloDefaultResponse = Awaited<ReturnType<typeof RootService.getHello>>;
export type RootServiceGetHelloQueryResult<TData = RootServiceGetHelloDefaultResponse, TError = unknown> = UseQueryResult<TData, TError>;
export const useRootServiceGetHelloKey = "RootServiceGetHello";
export const UseRootServiceGetHelloKeyFn = ({ xPrefectApiVersion }: {
  xPrefectApiVersion?: string;
} = {}, queryKey?: Array<unknown>) => [useRootServiceGetHelloKey, ...(queryKey ?? [{ xPrefectApiVersion }])];
export type RootServiceGetReadyDefaultResponse = Awaited<ReturnType<typeof RootService.getReady>>;
export type RootServiceGetReadyQueryResult<TData = RootServiceGetReadyDefaultResponse, TError = unknown> = UseQueryResult<TData, TError>;
export const useRootServiceGetReadyKey = "RootServiceGetReady";
export const UseRootServiceGetReadyKeyFn = ({ xPrefectApiVersion }: {
  xPrefectApiVersion?: string;
} = {}, queryKey?: Array<unknown>) => [useRootServiceGetReadyKey, ...(queryKey ?? [{ xPrefectApiVersion }])];
export type FlowsServiceGetFlowsByIdDefaultResponse = Awaited<ReturnType<typeof FlowsService.getFlowsById>>;
export type FlowsServiceGetFlowsByIdQueryResult<TData = FlowsServiceGetFlowsByIdDefaultResponse, TError = unknown> = UseQueryResult<TData, TError>;
export const useFlowsServiceGetFlowsByIdKey = "FlowsServiceGetFlowsById";
export const UseFlowsServiceGetFlowsByIdKeyFn = ({ id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}, queryKey?: Array<unknown>) => [useFlowsServiceGetFlowsByIdKey, ...(queryKey ?? [{ id, xPrefectApiVersion }])];
export type FlowsServiceGetFlowsNameByNameDefaultResponse = Awaited<ReturnType<typeof FlowsService.getFlowsNameByName>>;
export type FlowsServiceGetFlowsNameByNameQueryResult<TData = FlowsServiceGetFlowsNameByNameDefaultResponse, TError = unknown> = UseQueryResult<TData, TError>;
export const useFlowsServiceGetFlowsNameByNameKey = "FlowsServiceGetFlowsNameByName";
export const UseFlowsServiceGetFlowsNameByNameKeyFn = ({ name, xPrefectApiVersion }: {
  name: string;
  xPrefectApiVersion?: string;
}, queryKey?: Array<unknown>) => [useFlowsServiceGetFlowsNameByNameKey, ...(queryKey ?? [{ name, xPrefectApiVersion }])];
export type FlowRunsServiceGetFlowRunsByIdDefaultResponse = Awaited<ReturnType<typeof FlowRunsService.getFlowRunsById>>;
export type FlowRunsServiceGetFlowRunsByIdQueryResult<TData = FlowRunsServiceGetFlowRunsByIdDefaultResponse, TError = unknown> = UseQueryResult<TData, TError>;
export const useFlowRunsServiceGetFlowRunsByIdKey = "FlowRunsServiceGetFlowRunsById";
export const UseFlowRunsServiceGetFlowRunsByIdKeyFn = ({ id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}, queryKey?: Array<unknown>) => [useFlowRunsServiceGetFlowRunsByIdKey, ...(queryKey ?? [{ id, xPrefectApiVersion }])];
export type FlowRunsServiceGetFlowRunsByIdGraphDefaultResponse = Awaited<ReturnType<typeof FlowRunsService.getFlowRunsByIdGraph>>;
export type FlowRunsServiceGetFlowRunsByIdGraphQueryResult<TData = FlowRunsServiceGetFlowRunsByIdGraphDefaultResponse, TError = unknown> = UseQueryResult<TData, TError>;
export const useFlowRunsServiceGetFlowRunsByIdGraphKey = "FlowRunsServiceGetFlowRunsByIdGraph";
export const UseFlowRunsServiceGetFlowRunsByIdGraphKeyFn = ({ id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}, queryKey?: Array<unknown>) => [useFlowRunsServiceGetFlowRunsByIdGraphKey, ...(queryKey ?? [{ id, xPrefectApiVersion }])];
export type FlowRunsServiceGetFlowRunsByIdGraphV2DefaultResponse = Awaited<ReturnType<typeof FlowRunsService.getFlowRunsByIdGraphV2>>;
export type FlowRunsServiceGetFlowRunsByIdGraphV2QueryResult<TData = FlowRunsServiceGetFlowRunsByIdGraphV2DefaultResponse, TError = unknown> = UseQueryResult<TData, TError>;
export const useFlowRunsServiceGetFlowRunsByIdGraphV2Key = "FlowRunsServiceGetFlowRunsByIdGraphV2";
export const UseFlowRunsServiceGetFlowRunsByIdGraphV2KeyFn = ({ id, since, xPrefectApiVersion }: {
  id: string;
  since?: string;
  xPrefectApiVersion?: string;
}, queryKey?: Array<unknown>) => [useFlowRunsServiceGetFlowRunsByIdGraphV2Key, ...(queryKey ?? [{ id, since, xPrefectApiVersion }])];
export type FlowRunsServiceGetFlowRunsByIdInputByKeyDefaultResponse = Awaited<ReturnType<typeof FlowRunsService.getFlowRunsByIdInputByKey>>;
export type FlowRunsServiceGetFlowRunsByIdInputByKeyQueryResult<TData = FlowRunsServiceGetFlowRunsByIdInputByKeyDefaultResponse, TError = unknown> = UseQueryResult<TData, TError>;
export const useFlowRunsServiceGetFlowRunsByIdInputByKeyKey = "FlowRunsServiceGetFlowRunsByIdInputByKey";
export const UseFlowRunsServiceGetFlowRunsByIdInputByKeyKeyFn = ({ id, key, xPrefectApiVersion }: {
  id: string;
  key: string;
  xPrefectApiVersion?: string;
}, queryKey?: Array<unknown>) => [useFlowRunsServiceGetFlowRunsByIdInputByKeyKey, ...(queryKey ?? [{ id, key, xPrefectApiVersion }])];
export type FlowRunsServiceGetFlowRunsByIdLogsDownloadDefaultResponse = Awaited<ReturnType<typeof FlowRunsService.getFlowRunsByIdLogsDownload>>;
export type FlowRunsServiceGetFlowRunsByIdLogsDownloadQueryResult<TData = FlowRunsServiceGetFlowRunsByIdLogsDownloadDefaultResponse, TError = unknown> = UseQueryResult<TData, TError>;
export const useFlowRunsServiceGetFlowRunsByIdLogsDownloadKey = "FlowRunsServiceGetFlowRunsByIdLogsDownload";
export const UseFlowRunsServiceGetFlowRunsByIdLogsDownloadKeyFn = ({ id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}, queryKey?: Array<unknown>) => [useFlowRunsServiceGetFlowRunsByIdLogsDownloadKey, ...(queryKey ?? [{ id, xPrefectApiVersion }])];
export type TaskRunsServiceGetTaskRunsByIdDefaultResponse = Awaited<ReturnType<typeof TaskRunsService.getTaskRunsById>>;
export type TaskRunsServiceGetTaskRunsByIdQueryResult<TData = TaskRunsServiceGetTaskRunsByIdDefaultResponse, TError = unknown> = UseQueryResult<TData, TError>;
export const useTaskRunsServiceGetTaskRunsByIdKey = "TaskRunsServiceGetTaskRunsById";
export const UseTaskRunsServiceGetTaskRunsByIdKeyFn = ({ id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}, queryKey?: Array<unknown>) => [useTaskRunsServiceGetTaskRunsByIdKey, ...(queryKey ?? [{ id, xPrefectApiVersion }])];
export type FlowRunStatesServiceGetFlowRunStatesByIdDefaultResponse = Awaited<ReturnType<typeof FlowRunStatesService.getFlowRunStatesById>>;
export type FlowRunStatesServiceGetFlowRunStatesByIdQueryResult<TData = FlowRunStatesServiceGetFlowRunStatesByIdDefaultResponse, TError = unknown> = UseQueryResult<TData, TError>;
export const useFlowRunStatesServiceGetFlowRunStatesByIdKey = "FlowRunStatesServiceGetFlowRunStatesById";
export const UseFlowRunStatesServiceGetFlowRunStatesByIdKeyFn = ({ id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}, queryKey?: Array<unknown>) => [useFlowRunStatesServiceGetFlowRunStatesByIdKey, ...(queryKey ?? [{ id, xPrefectApiVersion }])];
export type FlowRunStatesServiceGetFlowRunStatesDefaultResponse = Awaited<ReturnType<typeof FlowRunStatesService.getFlowRunStates>>;
export type FlowRunStatesServiceGetFlowRunStatesQueryResult<TData = FlowRunStatesServiceGetFlowRunStatesDefaultResponse, TError = unknown> = UseQueryResult<TData, TError>;
export const useFlowRunStatesServiceGetFlowRunStatesKey = "FlowRunStatesServiceGetFlowRunStates";
export const UseFlowRunStatesServiceGetFlowRunStatesKeyFn = ({ flowRunId, xPrefectApiVersion }: {
  flowRunId: string;
  xPrefectApiVersion?: string;
}, queryKey?: Array<unknown>) => [useFlowRunStatesServiceGetFlowRunStatesKey, ...(queryKey ?? [{ flowRunId, xPrefectApiVersion }])];
export type TaskRunStatesServiceGetTaskRunStatesByIdDefaultResponse = Awaited<ReturnType<typeof TaskRunStatesService.getTaskRunStatesById>>;
export type TaskRunStatesServiceGetTaskRunStatesByIdQueryResult<TData = TaskRunStatesServiceGetTaskRunStatesByIdDefaultResponse, TError = unknown> = UseQueryResult<TData, TError>;
export const useTaskRunStatesServiceGetTaskRunStatesByIdKey = "TaskRunStatesServiceGetTaskRunStatesById";
export const UseTaskRunStatesServiceGetTaskRunStatesByIdKeyFn = ({ id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}, queryKey?: Array<unknown>) => [useTaskRunStatesServiceGetTaskRunStatesByIdKey, ...(queryKey ?? [{ id, xPrefectApiVersion }])];
export type TaskRunStatesServiceGetTaskRunStatesDefaultResponse = Awaited<ReturnType<typeof TaskRunStatesService.getTaskRunStates>>;
export type TaskRunStatesServiceGetTaskRunStatesQueryResult<TData = TaskRunStatesServiceGetTaskRunStatesDefaultResponse, TError = unknown> = UseQueryResult<TData, TError>;
export const useTaskRunStatesServiceGetTaskRunStatesKey = "TaskRunStatesServiceGetTaskRunStates";
export const UseTaskRunStatesServiceGetTaskRunStatesKeyFn = ({ taskRunId, xPrefectApiVersion }: {
  taskRunId: string;
  xPrefectApiVersion?: string;
}, queryKey?: Array<unknown>) => [useTaskRunStatesServiceGetTaskRunStatesKey, ...(queryKey ?? [{ taskRunId, xPrefectApiVersion }])];
export type FlowRunNotificationPoliciesServiceGetFlowRunNotificationPoliciesByIdDefaultResponse = Awaited<ReturnType<typeof FlowRunNotificationPoliciesService.getFlowRunNotificationPoliciesById>>;
export type FlowRunNotificationPoliciesServiceGetFlowRunNotificationPoliciesByIdQueryResult<TData = FlowRunNotificationPoliciesServiceGetFlowRunNotificationPoliciesByIdDefaultResponse, TError = unknown> = UseQueryResult<TData, TError>;
export const useFlowRunNotificationPoliciesServiceGetFlowRunNotificationPoliciesByIdKey = "FlowRunNotificationPoliciesServiceGetFlowRunNotificationPoliciesById";
export const UseFlowRunNotificationPoliciesServiceGetFlowRunNotificationPoliciesByIdKeyFn = ({ id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}, queryKey?: Array<unknown>) => [useFlowRunNotificationPoliciesServiceGetFlowRunNotificationPoliciesByIdKey, ...(queryKey ?? [{ id, xPrefectApiVersion }])];
export type DeploymentsServiceGetDeploymentsByIdDefaultResponse = Awaited<ReturnType<typeof DeploymentsService.getDeploymentsById>>;
export type DeploymentsServiceGetDeploymentsByIdQueryResult<TData = DeploymentsServiceGetDeploymentsByIdDefaultResponse, TError = unknown> = UseQueryResult<TData, TError>;
export const useDeploymentsServiceGetDeploymentsByIdKey = "DeploymentsServiceGetDeploymentsById";
export const UseDeploymentsServiceGetDeploymentsByIdKeyFn = ({ id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}, queryKey?: Array<unknown>) => [useDeploymentsServiceGetDeploymentsByIdKey, ...(queryKey ?? [{ id, xPrefectApiVersion }])];
export type DeploymentsServiceGetDeploymentsNameByFlowNameByDeploymentNameDefaultResponse = Awaited<ReturnType<typeof DeploymentsService.getDeploymentsNameByFlowNameByDeploymentName>>;
export type DeploymentsServiceGetDeploymentsNameByFlowNameByDeploymentNameQueryResult<TData = DeploymentsServiceGetDeploymentsNameByFlowNameByDeploymentNameDefaultResponse, TError = unknown> = UseQueryResult<TData, TError>;
export const useDeploymentsServiceGetDeploymentsNameByFlowNameByDeploymentNameKey = "DeploymentsServiceGetDeploymentsNameByFlowNameByDeploymentName";
export const UseDeploymentsServiceGetDeploymentsNameByFlowNameByDeploymentNameKeyFn = ({ deploymentName, flowName, xPrefectApiVersion }: {
  deploymentName: string;
  flowName: string;
  xPrefectApiVersion?: string;
}, queryKey?: Array<unknown>) => [useDeploymentsServiceGetDeploymentsNameByFlowNameByDeploymentNameKey, ...(queryKey ?? [{ deploymentName, flowName, xPrefectApiVersion }])];
export type DeploymentsServiceGetDeploymentsByIdWorkQueueCheckDefaultResponse = Awaited<ReturnType<typeof DeploymentsService.getDeploymentsByIdWorkQueueCheck>>;
export type DeploymentsServiceGetDeploymentsByIdWorkQueueCheckQueryResult<TData = DeploymentsServiceGetDeploymentsByIdWorkQueueCheckDefaultResponse, TError = unknown> = UseQueryResult<TData, TError>;
export const useDeploymentsServiceGetDeploymentsByIdWorkQueueCheckKey = "DeploymentsServiceGetDeploymentsByIdWorkQueueCheck";
export const UseDeploymentsServiceGetDeploymentsByIdWorkQueueCheckKeyFn = ({ id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}, queryKey?: Array<unknown>) => [useDeploymentsServiceGetDeploymentsByIdWorkQueueCheckKey, ...(queryKey ?? [{ id, xPrefectApiVersion }])];
export type DeploymentsServiceGetDeploymentsByIdSchedulesDefaultResponse = Awaited<ReturnType<typeof DeploymentsService.getDeploymentsByIdSchedules>>;
export type DeploymentsServiceGetDeploymentsByIdSchedulesQueryResult<TData = DeploymentsServiceGetDeploymentsByIdSchedulesDefaultResponse, TError = unknown> = UseQueryResult<TData, TError>;
export const useDeploymentsServiceGetDeploymentsByIdSchedulesKey = "DeploymentsServiceGetDeploymentsByIdSchedules";
export const UseDeploymentsServiceGetDeploymentsByIdSchedulesKeyFn = ({ id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}, queryKey?: Array<unknown>) => [useDeploymentsServiceGetDeploymentsByIdSchedulesKey, ...(queryKey ?? [{ id, xPrefectApiVersion }])];
export type SavedSearchesServiceGetSavedSearchesByIdDefaultResponse = Awaited<ReturnType<typeof SavedSearchesService.getSavedSearchesById>>;
export type SavedSearchesServiceGetSavedSearchesByIdQueryResult<TData = SavedSearchesServiceGetSavedSearchesByIdDefaultResponse, TError = unknown> = UseQueryResult<TData, TError>;
export const useSavedSearchesServiceGetSavedSearchesByIdKey = "SavedSearchesServiceGetSavedSearchesById";
export const UseSavedSearchesServiceGetSavedSearchesByIdKeyFn = ({ id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}, queryKey?: Array<unknown>) => [useSavedSearchesServiceGetSavedSearchesByIdKey, ...(queryKey ?? [{ id, xPrefectApiVersion }])];
export type ConcurrencyLimitsServiceGetConcurrencyLimitsByIdDefaultResponse = Awaited<ReturnType<typeof ConcurrencyLimitsService.getConcurrencyLimitsById>>;
export type ConcurrencyLimitsServiceGetConcurrencyLimitsByIdQueryResult<TData = ConcurrencyLimitsServiceGetConcurrencyLimitsByIdDefaultResponse, TError = unknown> = UseQueryResult<TData, TError>;
export const useConcurrencyLimitsServiceGetConcurrencyLimitsByIdKey = "ConcurrencyLimitsServiceGetConcurrencyLimitsById";
export const UseConcurrencyLimitsServiceGetConcurrencyLimitsByIdKeyFn = ({ id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}, queryKey?: Array<unknown>) => [useConcurrencyLimitsServiceGetConcurrencyLimitsByIdKey, ...(queryKey ?? [{ id, xPrefectApiVersion }])];
export type ConcurrencyLimitsServiceGetConcurrencyLimitsTagByTagDefaultResponse = Awaited<ReturnType<typeof ConcurrencyLimitsService.getConcurrencyLimitsTagByTag>>;
export type ConcurrencyLimitsServiceGetConcurrencyLimitsTagByTagQueryResult<TData = ConcurrencyLimitsServiceGetConcurrencyLimitsTagByTagDefaultResponse, TError = unknown> = UseQueryResult<TData, TError>;
export const useConcurrencyLimitsServiceGetConcurrencyLimitsTagByTagKey = "ConcurrencyLimitsServiceGetConcurrencyLimitsTagByTag";
export const UseConcurrencyLimitsServiceGetConcurrencyLimitsTagByTagKeyFn = ({ tag, xPrefectApiVersion }: {
  tag: string;
  xPrefectApiVersion?: string;
}, queryKey?: Array<unknown>) => [useConcurrencyLimitsServiceGetConcurrencyLimitsTagByTagKey, ...(queryKey ?? [{ tag, xPrefectApiVersion }])];
export type ConcurrencyLimitsV2ServiceGetV2ConcurrencyLimitsByIdOrNameDefaultResponse = Awaited<ReturnType<typeof ConcurrencyLimitsV2Service.getV2ConcurrencyLimitsByIdOrName>>;
export type ConcurrencyLimitsV2ServiceGetV2ConcurrencyLimitsByIdOrNameQueryResult<TData = ConcurrencyLimitsV2ServiceGetV2ConcurrencyLimitsByIdOrNameDefaultResponse, TError = unknown> = UseQueryResult<TData, TError>;
export const useConcurrencyLimitsV2ServiceGetV2ConcurrencyLimitsByIdOrNameKey = "ConcurrencyLimitsV2ServiceGetV2ConcurrencyLimitsByIdOrName";
export const UseConcurrencyLimitsV2ServiceGetV2ConcurrencyLimitsByIdOrNameKeyFn = ({ idOrName, xPrefectApiVersion }: {
  idOrName: string;
  xPrefectApiVersion?: string;
}, queryKey?: Array<unknown>) => [useConcurrencyLimitsV2ServiceGetV2ConcurrencyLimitsByIdOrNameKey, ...(queryKey ?? [{ idOrName, xPrefectApiVersion }])];
export type BlockTypesServiceGetBlockTypesByIdDefaultResponse = Awaited<ReturnType<typeof BlockTypesService.getBlockTypesById>>;
export type BlockTypesServiceGetBlockTypesByIdQueryResult<TData = BlockTypesServiceGetBlockTypesByIdDefaultResponse, TError = unknown> = UseQueryResult<TData, TError>;
export const useBlockTypesServiceGetBlockTypesByIdKey = "BlockTypesServiceGetBlockTypesById";
export const UseBlockTypesServiceGetBlockTypesByIdKeyFn = ({ id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}, queryKey?: Array<unknown>) => [useBlockTypesServiceGetBlockTypesByIdKey, ...(queryKey ?? [{ id, xPrefectApiVersion }])];
export type BlockTypesServiceGetBlockTypesSlugBySlugDefaultResponse = Awaited<ReturnType<typeof BlockTypesService.getBlockTypesSlugBySlug>>;
export type BlockTypesServiceGetBlockTypesSlugBySlugQueryResult<TData = BlockTypesServiceGetBlockTypesSlugBySlugDefaultResponse, TError = unknown> = UseQueryResult<TData, TError>;
export const useBlockTypesServiceGetBlockTypesSlugBySlugKey = "BlockTypesServiceGetBlockTypesSlugBySlug";
export const UseBlockTypesServiceGetBlockTypesSlugBySlugKeyFn = ({ slug, xPrefectApiVersion }: {
  slug: string;
  xPrefectApiVersion?: string;
}, queryKey?: Array<unknown>) => [useBlockTypesServiceGetBlockTypesSlugBySlugKey, ...(queryKey ?? [{ slug, xPrefectApiVersion }])];
export type BlockTypesServiceGetBlockTypesSlugBySlugBlockDocumentsDefaultResponse = Awaited<ReturnType<typeof BlockTypesService.getBlockTypesSlugBySlugBlockDocuments>>;
export type BlockTypesServiceGetBlockTypesSlugBySlugBlockDocumentsQueryResult<TData = BlockTypesServiceGetBlockTypesSlugBySlugBlockDocumentsDefaultResponse, TError = unknown> = UseQueryResult<TData, TError>;
export const useBlockTypesServiceGetBlockTypesSlugBySlugBlockDocumentsKey = "BlockTypesServiceGetBlockTypesSlugBySlugBlockDocuments";
export const UseBlockTypesServiceGetBlockTypesSlugBySlugBlockDocumentsKeyFn = ({ includeSecrets, slug, xPrefectApiVersion }: {
  includeSecrets?: boolean;
  slug: string;
  xPrefectApiVersion?: string;
}, queryKey?: Array<unknown>) => [useBlockTypesServiceGetBlockTypesSlugBySlugBlockDocumentsKey, ...(queryKey ?? [{ includeSecrets, slug, xPrefectApiVersion }])];
export type BlockTypesServiceGetBlockTypesSlugBySlugBlockDocumentsNameByBlockDocumentNameDefaultResponse = Awaited<ReturnType<typeof BlockTypesService.getBlockTypesSlugBySlugBlockDocumentsNameByBlockDocumentName>>;
export type BlockTypesServiceGetBlockTypesSlugBySlugBlockDocumentsNameByBlockDocumentNameQueryResult<TData = BlockTypesServiceGetBlockTypesSlugBySlugBlockDocumentsNameByBlockDocumentNameDefaultResponse, TError = unknown> = UseQueryResult<TData, TError>;
export const useBlockTypesServiceGetBlockTypesSlugBySlugBlockDocumentsNameByBlockDocumentNameKey = "BlockTypesServiceGetBlockTypesSlugBySlugBlockDocumentsNameByBlockDocumentName";
export const UseBlockTypesServiceGetBlockTypesSlugBySlugBlockDocumentsNameByBlockDocumentNameKeyFn = ({ blockDocumentName, includeSecrets, slug, xPrefectApiVersion }: {
  blockDocumentName: string;
  includeSecrets?: boolean;
  slug: string;
  xPrefectApiVersion?: string;
}, queryKey?: Array<unknown>) => [useBlockTypesServiceGetBlockTypesSlugBySlugBlockDocumentsNameByBlockDocumentNameKey, ...(queryKey ?? [{ blockDocumentName, includeSecrets, slug, xPrefectApiVersion }])];
export type BlockDocumentsServiceGetBlockTypesSlugBySlugBlockDocumentsDefaultResponse = Awaited<ReturnType<typeof BlockDocumentsService.getBlockTypesSlugBySlugBlockDocuments>>;
export type BlockDocumentsServiceGetBlockTypesSlugBySlugBlockDocumentsQueryResult<TData = BlockDocumentsServiceGetBlockTypesSlugBySlugBlockDocumentsDefaultResponse, TError = unknown> = UseQueryResult<TData, TError>;
export const useBlockDocumentsServiceGetBlockTypesSlugBySlugBlockDocumentsKey = "BlockDocumentsServiceGetBlockTypesSlugBySlugBlockDocuments";
export const UseBlockDocumentsServiceGetBlockTypesSlugBySlugBlockDocumentsKeyFn = ({ includeSecrets, slug, xPrefectApiVersion }: {
  includeSecrets?: boolean;
  slug: string;
  xPrefectApiVersion?: string;
}, queryKey?: Array<unknown>) => [useBlockDocumentsServiceGetBlockTypesSlugBySlugBlockDocumentsKey, ...(queryKey ?? [{ includeSecrets, slug, xPrefectApiVersion }])];
export type BlockDocumentsServiceGetBlockTypesSlugBySlugBlockDocumentsNameByBlockDocumentNameDefaultResponse = Awaited<ReturnType<typeof BlockDocumentsService.getBlockTypesSlugBySlugBlockDocumentsNameByBlockDocumentName>>;
export type BlockDocumentsServiceGetBlockTypesSlugBySlugBlockDocumentsNameByBlockDocumentNameQueryResult<TData = BlockDocumentsServiceGetBlockTypesSlugBySlugBlockDocumentsNameByBlockDocumentNameDefaultResponse, TError = unknown> = UseQueryResult<TData, TError>;
export const useBlockDocumentsServiceGetBlockTypesSlugBySlugBlockDocumentsNameByBlockDocumentNameKey = "BlockDocumentsServiceGetBlockTypesSlugBySlugBlockDocumentsNameByBlockDocumentName";
export const UseBlockDocumentsServiceGetBlockTypesSlugBySlugBlockDocumentsNameByBlockDocumentNameKeyFn = ({ blockDocumentName, includeSecrets, slug, xPrefectApiVersion }: {
  blockDocumentName: string;
  includeSecrets?: boolean;
  slug: string;
  xPrefectApiVersion?: string;
}, queryKey?: Array<unknown>) => [useBlockDocumentsServiceGetBlockTypesSlugBySlugBlockDocumentsNameByBlockDocumentNameKey, ...(queryKey ?? [{ blockDocumentName, includeSecrets, slug, xPrefectApiVersion }])];
export type BlockDocumentsServiceGetBlockDocumentsByIdDefaultResponse = Awaited<ReturnType<typeof BlockDocumentsService.getBlockDocumentsById>>;
export type BlockDocumentsServiceGetBlockDocumentsByIdQueryResult<TData = BlockDocumentsServiceGetBlockDocumentsByIdDefaultResponse, TError = unknown> = UseQueryResult<TData, TError>;
export const useBlockDocumentsServiceGetBlockDocumentsByIdKey = "BlockDocumentsServiceGetBlockDocumentsById";
export const UseBlockDocumentsServiceGetBlockDocumentsByIdKeyFn = ({ id, includeSecrets, xPrefectApiVersion }: {
  id: string;
  includeSecrets?: boolean;
  xPrefectApiVersion?: string;
}, queryKey?: Array<unknown>) => [useBlockDocumentsServiceGetBlockDocumentsByIdKey, ...(queryKey ?? [{ id, includeSecrets, xPrefectApiVersion }])];
export type WorkPoolsServiceGetWorkPoolsByNameDefaultResponse = Awaited<ReturnType<typeof WorkPoolsService.getWorkPoolsByName>>;
export type WorkPoolsServiceGetWorkPoolsByNameQueryResult<TData = WorkPoolsServiceGetWorkPoolsByNameDefaultResponse, TError = unknown> = UseQueryResult<TData, TError>;
export const useWorkPoolsServiceGetWorkPoolsByNameKey = "WorkPoolsServiceGetWorkPoolsByName";
export const UseWorkPoolsServiceGetWorkPoolsByNameKeyFn = ({ name, xPrefectApiVersion }: {
  name: string;
  xPrefectApiVersion?: string;
}, queryKey?: Array<unknown>) => [useWorkPoolsServiceGetWorkPoolsByNameKey, ...(queryKey ?? [{ name, xPrefectApiVersion }])];
export type WorkPoolsServiceGetWorkPoolsByWorkPoolNameQueuesByNameDefaultResponse = Awaited<ReturnType<typeof WorkPoolsService.getWorkPoolsByWorkPoolNameQueuesByName>>;
export type WorkPoolsServiceGetWorkPoolsByWorkPoolNameQueuesByNameQueryResult<TData = WorkPoolsServiceGetWorkPoolsByWorkPoolNameQueuesByNameDefaultResponse, TError = unknown> = UseQueryResult<TData, TError>;
export const useWorkPoolsServiceGetWorkPoolsByWorkPoolNameQueuesByNameKey = "WorkPoolsServiceGetWorkPoolsByWorkPoolNameQueuesByName";
export const UseWorkPoolsServiceGetWorkPoolsByWorkPoolNameQueuesByNameKeyFn = ({ name, workPoolName, xPrefectApiVersion }: {
  name: string;
  workPoolName: string;
  xPrefectApiVersion?: string;
}, queryKey?: Array<unknown>) => [useWorkPoolsServiceGetWorkPoolsByWorkPoolNameQueuesByNameKey, ...(queryKey ?? [{ name, workPoolName, xPrefectApiVersion }])];
export type WorkQueuesServiceGetWorkQueuesByIdDefaultResponse = Awaited<ReturnType<typeof WorkQueuesService.getWorkQueuesById>>;
export type WorkQueuesServiceGetWorkQueuesByIdQueryResult<TData = WorkQueuesServiceGetWorkQueuesByIdDefaultResponse, TError = unknown> = UseQueryResult<TData, TError>;
export const useWorkQueuesServiceGetWorkQueuesByIdKey = "WorkQueuesServiceGetWorkQueuesById";
export const UseWorkQueuesServiceGetWorkQueuesByIdKeyFn = ({ id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}, queryKey?: Array<unknown>) => [useWorkQueuesServiceGetWorkQueuesByIdKey, ...(queryKey ?? [{ id, xPrefectApiVersion }])];
export type WorkQueuesServiceGetWorkQueuesNameByNameDefaultResponse = Awaited<ReturnType<typeof WorkQueuesService.getWorkQueuesNameByName>>;
export type WorkQueuesServiceGetWorkQueuesNameByNameQueryResult<TData = WorkQueuesServiceGetWorkQueuesNameByNameDefaultResponse, TError = unknown> = UseQueryResult<TData, TError>;
export const useWorkQueuesServiceGetWorkQueuesNameByNameKey = "WorkQueuesServiceGetWorkQueuesNameByName";
export const UseWorkQueuesServiceGetWorkQueuesNameByNameKeyFn = ({ name, xPrefectApiVersion }: {
  name: string;
  xPrefectApiVersion?: string;
}, queryKey?: Array<unknown>) => [useWorkQueuesServiceGetWorkQueuesNameByNameKey, ...(queryKey ?? [{ name, xPrefectApiVersion }])];
export type WorkQueuesServiceGetWorkQueuesByIdStatusDefaultResponse = Awaited<ReturnType<typeof WorkQueuesService.getWorkQueuesByIdStatus>>;
export type WorkQueuesServiceGetWorkQueuesByIdStatusQueryResult<TData = WorkQueuesServiceGetWorkQueuesByIdStatusDefaultResponse, TError = unknown> = UseQueryResult<TData, TError>;
export const useWorkQueuesServiceGetWorkQueuesByIdStatusKey = "WorkQueuesServiceGetWorkQueuesByIdStatus";
export const UseWorkQueuesServiceGetWorkQueuesByIdStatusKeyFn = ({ id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}, queryKey?: Array<unknown>) => [useWorkQueuesServiceGetWorkQueuesByIdStatusKey, ...(queryKey ?? [{ id, xPrefectApiVersion }])];
export type ArtifactsServiceGetArtifactsByIdDefaultResponse = Awaited<ReturnType<typeof ArtifactsService.getArtifactsById>>;
export type ArtifactsServiceGetArtifactsByIdQueryResult<TData = ArtifactsServiceGetArtifactsByIdDefaultResponse, TError = unknown> = UseQueryResult<TData, TError>;
export const useArtifactsServiceGetArtifactsByIdKey = "ArtifactsServiceGetArtifactsById";
export const UseArtifactsServiceGetArtifactsByIdKeyFn = ({ id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}, queryKey?: Array<unknown>) => [useArtifactsServiceGetArtifactsByIdKey, ...(queryKey ?? [{ id, xPrefectApiVersion }])];
export type ArtifactsServiceGetArtifactsByKeyLatestDefaultResponse = Awaited<ReturnType<typeof ArtifactsService.getArtifactsByKeyLatest>>;
export type ArtifactsServiceGetArtifactsByKeyLatestQueryResult<TData = ArtifactsServiceGetArtifactsByKeyLatestDefaultResponse, TError = unknown> = UseQueryResult<TData, TError>;
export const useArtifactsServiceGetArtifactsByKeyLatestKey = "ArtifactsServiceGetArtifactsByKeyLatest";
export const UseArtifactsServiceGetArtifactsByKeyLatestKeyFn = ({ key, xPrefectApiVersion }: {
  key: string;
  xPrefectApiVersion?: string;
}, queryKey?: Array<unknown>) => [useArtifactsServiceGetArtifactsByKeyLatestKey, ...(queryKey ?? [{ key, xPrefectApiVersion }])];
export type BlockSchemasServiceGetBlockSchemasByIdDefaultResponse = Awaited<ReturnType<typeof BlockSchemasService.getBlockSchemasById>>;
export type BlockSchemasServiceGetBlockSchemasByIdQueryResult<TData = BlockSchemasServiceGetBlockSchemasByIdDefaultResponse, TError = unknown> = UseQueryResult<TData, TError>;
export const useBlockSchemasServiceGetBlockSchemasByIdKey = "BlockSchemasServiceGetBlockSchemasById";
export const UseBlockSchemasServiceGetBlockSchemasByIdKeyFn = ({ id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}, queryKey?: Array<unknown>) => [useBlockSchemasServiceGetBlockSchemasByIdKey, ...(queryKey ?? [{ id, xPrefectApiVersion }])];
export type BlockSchemasServiceGetBlockSchemasChecksumByChecksumDefaultResponse = Awaited<ReturnType<typeof BlockSchemasService.getBlockSchemasChecksumByChecksum>>;
export type BlockSchemasServiceGetBlockSchemasChecksumByChecksumQueryResult<TData = BlockSchemasServiceGetBlockSchemasChecksumByChecksumDefaultResponse, TError = unknown> = UseQueryResult<TData, TError>;
export const useBlockSchemasServiceGetBlockSchemasChecksumByChecksumKey = "BlockSchemasServiceGetBlockSchemasChecksumByChecksum";
export const UseBlockSchemasServiceGetBlockSchemasChecksumByChecksumKeyFn = ({ checksum, version, xPrefectApiVersion }: {
  checksum: string;
  version?: string;
  xPrefectApiVersion?: string;
}, queryKey?: Array<unknown>) => [useBlockSchemasServiceGetBlockSchemasChecksumByChecksumKey, ...(queryKey ?? [{ checksum, version, xPrefectApiVersion }])];
export type BlockCapabilitiesServiceGetBlockCapabilitiesDefaultResponse = Awaited<ReturnType<typeof BlockCapabilitiesService.getBlockCapabilities>>;
export type BlockCapabilitiesServiceGetBlockCapabilitiesQueryResult<TData = BlockCapabilitiesServiceGetBlockCapabilitiesDefaultResponse, TError = unknown> = UseQueryResult<TData, TError>;
export const useBlockCapabilitiesServiceGetBlockCapabilitiesKey = "BlockCapabilitiesServiceGetBlockCapabilities";
export const UseBlockCapabilitiesServiceGetBlockCapabilitiesKeyFn = ({ xPrefectApiVersion }: {
  xPrefectApiVersion?: string;
} = {}, queryKey?: Array<unknown>) => [useBlockCapabilitiesServiceGetBlockCapabilitiesKey, ...(queryKey ?? [{ xPrefectApiVersion }])];
export type CollectionsServiceGetCollectionsViewsByViewDefaultResponse = Awaited<ReturnType<typeof CollectionsService.getCollectionsViewsByView>>;
export type CollectionsServiceGetCollectionsViewsByViewQueryResult<TData = CollectionsServiceGetCollectionsViewsByViewDefaultResponse, TError = unknown> = UseQueryResult<TData, TError>;
export const useCollectionsServiceGetCollectionsViewsByViewKey = "CollectionsServiceGetCollectionsViewsByView";
export const UseCollectionsServiceGetCollectionsViewsByViewKeyFn = ({ view, xPrefectApiVersion }: {
  view: string;
  xPrefectApiVersion?: string;
}, queryKey?: Array<unknown>) => [useCollectionsServiceGetCollectionsViewsByViewKey, ...(queryKey ?? [{ view, xPrefectApiVersion }])];
export type VariablesServiceGetVariablesByIdDefaultResponse = Awaited<ReturnType<typeof VariablesService.getVariablesById>>;
export type VariablesServiceGetVariablesByIdQueryResult<TData = VariablesServiceGetVariablesByIdDefaultResponse, TError = unknown> = UseQueryResult<TData, TError>;
export const useVariablesServiceGetVariablesByIdKey = "VariablesServiceGetVariablesById";
export const UseVariablesServiceGetVariablesByIdKeyFn = ({ id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}, queryKey?: Array<unknown>) => [useVariablesServiceGetVariablesByIdKey, ...(queryKey ?? [{ id, xPrefectApiVersion }])];
export type VariablesServiceGetVariablesNameByNameDefaultResponse = Awaited<ReturnType<typeof VariablesService.getVariablesNameByName>>;
export type VariablesServiceGetVariablesNameByNameQueryResult<TData = VariablesServiceGetVariablesNameByNameDefaultResponse, TError = unknown> = UseQueryResult<TData, TError>;
export const useVariablesServiceGetVariablesNameByNameKey = "VariablesServiceGetVariablesNameByName";
export const UseVariablesServiceGetVariablesNameByNameKeyFn = ({ name, xPrefectApiVersion }: {
  name: string;
  xPrefectApiVersion?: string;
}, queryKey?: Array<unknown>) => [useVariablesServiceGetVariablesNameByNameKey, ...(queryKey ?? [{ name, xPrefectApiVersion }])];
export type DefaultServiceGetCsrfTokenDefaultResponse = Awaited<ReturnType<typeof DefaultService.getCsrfToken>>;
export type DefaultServiceGetCsrfTokenQueryResult<TData = DefaultServiceGetCsrfTokenDefaultResponse, TError = unknown> = UseQueryResult<TData, TError>;
export const useDefaultServiceGetCsrfTokenKey = "DefaultServiceGetCsrfToken";
export const UseDefaultServiceGetCsrfTokenKeyFn = ({ client, xPrefectApiVersion }: {
  client: string;
  xPrefectApiVersion?: string;
}, queryKey?: Array<unknown>) => [useDefaultServiceGetCsrfTokenKey, ...(queryKey ?? [{ client, xPrefectApiVersion }])];
export type EventsServiceGetEventsFilterNextDefaultResponse = Awaited<ReturnType<typeof EventsService.getEventsFilterNext>>;
export type EventsServiceGetEventsFilterNextQueryResult<TData = EventsServiceGetEventsFilterNextDefaultResponse, TError = unknown> = UseQueryResult<TData, TError>;
export const useEventsServiceGetEventsFilterNextKey = "EventsServiceGetEventsFilterNext";
export const UseEventsServiceGetEventsFilterNextKeyFn = ({ pageToken, xPrefectApiVersion }: {
  pageToken: string;
  xPrefectApiVersion?: string;
}, queryKey?: Array<unknown>) => [useEventsServiceGetEventsFilterNextKey, ...(queryKey ?? [{ pageToken, xPrefectApiVersion }])];
export type AutomationsServiceGetAutomationsByIdDefaultResponse = Awaited<ReturnType<typeof AutomationsService.getAutomationsById>>;
export type AutomationsServiceGetAutomationsByIdQueryResult<TData = AutomationsServiceGetAutomationsByIdDefaultResponse, TError = unknown> = UseQueryResult<TData, TError>;
export const useAutomationsServiceGetAutomationsByIdKey = "AutomationsServiceGetAutomationsById";
export const UseAutomationsServiceGetAutomationsByIdKeyFn = ({ id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}, queryKey?: Array<unknown>) => [useAutomationsServiceGetAutomationsByIdKey, ...(queryKey ?? [{ id, xPrefectApiVersion }])];
export type AutomationsServiceGetAutomationsRelatedToByResourceIdDefaultResponse = Awaited<ReturnType<typeof AutomationsService.getAutomationsRelatedToByResourceId>>;
export type AutomationsServiceGetAutomationsRelatedToByResourceIdQueryResult<TData = AutomationsServiceGetAutomationsRelatedToByResourceIdDefaultResponse, TError = unknown> = UseQueryResult<TData, TError>;
export const useAutomationsServiceGetAutomationsRelatedToByResourceIdKey = "AutomationsServiceGetAutomationsRelatedToByResourceId";
export const UseAutomationsServiceGetAutomationsRelatedToByResourceIdKeyFn = ({ resourceId, xPrefectApiVersion }: {
  resourceId: string;
  xPrefectApiVersion?: string;
}, queryKey?: Array<unknown>) => [useAutomationsServiceGetAutomationsRelatedToByResourceIdKey, ...(queryKey ?? [{ resourceId, xPrefectApiVersion }])];
export type AdminServiceGetAdminSettingsDefaultResponse = Awaited<ReturnType<typeof AdminService.getAdminSettings>>;
export type AdminServiceGetAdminSettingsQueryResult<TData = AdminServiceGetAdminSettingsDefaultResponse, TError = unknown> = UseQueryResult<TData, TError>;
export const useAdminServiceGetAdminSettingsKey = "AdminServiceGetAdminSettings";
export const UseAdminServiceGetAdminSettingsKeyFn = ({ xPrefectApiVersion }: {
  xPrefectApiVersion?: string;
} = {}, queryKey?: Array<unknown>) => [useAdminServiceGetAdminSettingsKey, ...(queryKey ?? [{ xPrefectApiVersion }])];
export type AdminServiceGetAdminVersionDefaultResponse = Awaited<ReturnType<typeof AdminService.getAdminVersion>>;
export type AdminServiceGetAdminVersionQueryResult<TData = AdminServiceGetAdminVersionDefaultResponse, TError = unknown> = UseQueryResult<TData, TError>;
export const useAdminServiceGetAdminVersionKey = "AdminServiceGetAdminVersion";
export const UseAdminServiceGetAdminVersionKeyFn = ({ xPrefectApiVersion }: {
  xPrefectApiVersion?: string;
} = {}, queryKey?: Array<unknown>) => [useAdminServiceGetAdminVersionKey, ...(queryKey ?? [{ xPrefectApiVersion }])];
export type FlowsServicePostFlowsMutationResult = Awaited<ReturnType<typeof FlowsService.postFlows>>;
export type FlowsServicePostFlowsCountMutationResult = Awaited<ReturnType<typeof FlowsService.postFlowsCount>>;
export type FlowsServicePostFlowsFilterMutationResult = Awaited<ReturnType<typeof FlowsService.postFlowsFilter>>;
export type FlowsServicePostFlowsPaginateMutationResult = Awaited<ReturnType<typeof FlowsService.postFlowsPaginate>>;
export type FlowsServicePostUiFlowsCountDeploymentsMutationResult = Awaited<ReturnType<typeof FlowsService.postUiFlowsCountDeployments>>;
export type FlowsServicePostUiFlowsNextRunsMutationResult = Awaited<ReturnType<typeof FlowsService.postUiFlowsNextRuns>>;
export type FlowRunsServicePostFlowRunsMutationResult = Awaited<ReturnType<typeof FlowRunsService.postFlowRuns>>;
export type FlowRunsServicePostFlowRunsCountMutationResult = Awaited<ReturnType<typeof FlowRunsService.postFlowRunsCount>>;
export type FlowRunsServicePostFlowRunsLatenessMutationResult = Awaited<ReturnType<typeof FlowRunsService.postFlowRunsLateness>>;
export type FlowRunsServicePostFlowRunsHistoryMutationResult = Awaited<ReturnType<typeof FlowRunsService.postFlowRunsHistory>>;
export type FlowRunsServicePostFlowRunsByIdResumeMutationResult = Awaited<ReturnType<typeof FlowRunsService.postFlowRunsByIdResume>>;
export type FlowRunsServicePostFlowRunsFilterMutationResult = Awaited<ReturnType<typeof FlowRunsService.postFlowRunsFilter>>;
export type FlowRunsServicePostFlowRunsByIdSetStateMutationResult = Awaited<ReturnType<typeof FlowRunsService.postFlowRunsByIdSetState>>;
export type FlowRunsServicePostFlowRunsByIdInputMutationResult = Awaited<ReturnType<typeof FlowRunsService.postFlowRunsByIdInput>>;
export type FlowRunsServicePostFlowRunsByIdInputFilterMutationResult = Awaited<ReturnType<typeof FlowRunsService.postFlowRunsByIdInputFilter>>;
export type FlowRunsServicePostFlowRunsPaginateMutationResult = Awaited<ReturnType<typeof FlowRunsService.postFlowRunsPaginate>>;
export type FlowRunsServicePostUiFlowRunsHistoryMutationResult = Awaited<ReturnType<typeof FlowRunsService.postUiFlowRunsHistory>>;
export type FlowRunsServicePostUiFlowRunsCountTaskRunsMutationResult = Awaited<ReturnType<typeof FlowRunsService.postUiFlowRunsCountTaskRuns>>;
export type TaskRunsServicePostTaskRunsMutationResult = Awaited<ReturnType<typeof TaskRunsService.postTaskRuns>>;
export type TaskRunsServicePostTaskRunsCountMutationResult = Awaited<ReturnType<typeof TaskRunsService.postTaskRunsCount>>;
export type TaskRunsServicePostTaskRunsHistoryMutationResult = Awaited<ReturnType<typeof TaskRunsService.postTaskRunsHistory>>;
export type TaskRunsServicePostTaskRunsFilterMutationResult = Awaited<ReturnType<typeof TaskRunsService.postTaskRunsFilter>>;
export type TaskRunsServicePostTaskRunsByIdSetStateMutationResult = Awaited<ReturnType<typeof TaskRunsService.postTaskRunsByIdSetState>>;
export type TaskRunsServicePostUiTaskRunsDashboardCountsMutationResult = Awaited<ReturnType<typeof TaskRunsService.postUiTaskRunsDashboardCounts>>;
export type TaskRunsServicePostUiTaskRunsCountMutationResult = Awaited<ReturnType<typeof TaskRunsService.postUiTaskRunsCount>>;
export type FlowRunNotificationPoliciesServicePostFlowRunNotificationPoliciesMutationResult = Awaited<ReturnType<typeof FlowRunNotificationPoliciesService.postFlowRunNotificationPolicies>>;
export type FlowRunNotificationPoliciesServicePostFlowRunNotificationPoliciesFilterMutationResult = Awaited<ReturnType<typeof FlowRunNotificationPoliciesService.postFlowRunNotificationPoliciesFilter>>;
export type DeploymentsServicePostDeploymentsMutationResult = Awaited<ReturnType<typeof DeploymentsService.postDeployments>>;
export type DeploymentsServicePostDeploymentsFilterMutationResult = Awaited<ReturnType<typeof DeploymentsService.postDeploymentsFilter>>;
export type DeploymentsServicePostDeploymentsPaginateMutationResult = Awaited<ReturnType<typeof DeploymentsService.postDeploymentsPaginate>>;
export type DeploymentsServicePostDeploymentsGetScheduledFlowRunsMutationResult = Awaited<ReturnType<typeof DeploymentsService.postDeploymentsGetScheduledFlowRuns>>;
export type DeploymentsServicePostDeploymentsCountMutationResult = Awaited<ReturnType<typeof DeploymentsService.postDeploymentsCount>>;
export type DeploymentsServicePostDeploymentsByIdScheduleMutationResult = Awaited<ReturnType<typeof DeploymentsService.postDeploymentsByIdSchedule>>;
export type DeploymentsServicePostDeploymentsByIdResumeDeploymentMutationResult = Awaited<ReturnType<typeof DeploymentsService.postDeploymentsByIdResumeDeployment>>;
export type DeploymentsServicePostDeploymentsByIdPauseDeploymentMutationResult = Awaited<ReturnType<typeof DeploymentsService.postDeploymentsByIdPauseDeployment>>;
export type DeploymentsServicePostDeploymentsByIdCreateFlowRunMutationResult = Awaited<ReturnType<typeof DeploymentsService.postDeploymentsByIdCreateFlowRun>>;
export type DeploymentsServicePostDeploymentsByIdSchedulesMutationResult = Awaited<ReturnType<typeof DeploymentsService.postDeploymentsByIdSchedules>>;
export type SavedSearchesServicePostSavedSearchesFilterMutationResult = Awaited<ReturnType<typeof SavedSearchesService.postSavedSearchesFilter>>;
export type LogsServicePostLogsMutationResult = Awaited<ReturnType<typeof LogsService.postLogs>>;
export type LogsServicePostLogsFilterMutationResult = Awaited<ReturnType<typeof LogsService.postLogsFilter>>;
export type ConcurrencyLimitsServicePostConcurrencyLimitsMutationResult = Awaited<ReturnType<typeof ConcurrencyLimitsService.postConcurrencyLimits>>;
export type ConcurrencyLimitsServicePostConcurrencyLimitsFilterMutationResult = Awaited<ReturnType<typeof ConcurrencyLimitsService.postConcurrencyLimitsFilter>>;
export type ConcurrencyLimitsServicePostConcurrencyLimitsTagByTagResetMutationResult = Awaited<ReturnType<typeof ConcurrencyLimitsService.postConcurrencyLimitsTagByTagReset>>;
export type ConcurrencyLimitsServicePostConcurrencyLimitsIncrementMutationResult = Awaited<ReturnType<typeof ConcurrencyLimitsService.postConcurrencyLimitsIncrement>>;
export type ConcurrencyLimitsServicePostConcurrencyLimitsDecrementMutationResult = Awaited<ReturnType<typeof ConcurrencyLimitsService.postConcurrencyLimitsDecrement>>;
export type ConcurrencyLimitsV2ServicePostV2ConcurrencyLimitsMutationResult = Awaited<ReturnType<typeof ConcurrencyLimitsV2Service.postV2ConcurrencyLimits>>;
export type ConcurrencyLimitsV2ServicePostV2ConcurrencyLimitsFilterMutationResult = Awaited<ReturnType<typeof ConcurrencyLimitsV2Service.postV2ConcurrencyLimitsFilter>>;
export type ConcurrencyLimitsV2ServicePostV2ConcurrencyLimitsIncrementMutationResult = Awaited<ReturnType<typeof ConcurrencyLimitsV2Service.postV2ConcurrencyLimitsIncrement>>;
export type ConcurrencyLimitsV2ServicePostV2ConcurrencyLimitsDecrementMutationResult = Awaited<ReturnType<typeof ConcurrencyLimitsV2Service.postV2ConcurrencyLimitsDecrement>>;
export type BlockTypesServicePostBlockTypesMutationResult = Awaited<ReturnType<typeof BlockTypesService.postBlockTypes>>;
export type BlockTypesServicePostBlockTypesFilterMutationResult = Awaited<ReturnType<typeof BlockTypesService.postBlockTypesFilter>>;
export type BlockTypesServicePostBlockTypesInstallSystemBlockTypesMutationResult = Awaited<ReturnType<typeof BlockTypesService.postBlockTypesInstallSystemBlockTypes>>;
export type BlockDocumentsServicePostBlockDocumentsMutationResult = Awaited<ReturnType<typeof BlockDocumentsService.postBlockDocuments>>;
export type BlockDocumentsServicePostBlockDocumentsFilterMutationResult = Awaited<ReturnType<typeof BlockDocumentsService.postBlockDocumentsFilter>>;
export type BlockDocumentsServicePostBlockDocumentsCountMutationResult = Awaited<ReturnType<typeof BlockDocumentsService.postBlockDocumentsCount>>;
export type WorkPoolsServicePostWorkPoolsMutationResult = Awaited<ReturnType<typeof WorkPoolsService.postWorkPools>>;
export type WorkPoolsServicePostWorkPoolsFilterMutationResult = Awaited<ReturnType<typeof WorkPoolsService.postWorkPoolsFilter>>;
export type WorkPoolsServicePostWorkPoolsCountMutationResult = Awaited<ReturnType<typeof WorkPoolsService.postWorkPoolsCount>>;
export type WorkPoolsServicePostWorkPoolsByNameGetScheduledFlowRunsMutationResult = Awaited<ReturnType<typeof WorkPoolsService.postWorkPoolsByNameGetScheduledFlowRuns>>;
export type WorkPoolsServicePostWorkPoolsByWorkPoolNameQueuesMutationResult = Awaited<ReturnType<typeof WorkPoolsService.postWorkPoolsByWorkPoolNameQueues>>;
export type WorkPoolsServicePostWorkPoolsByWorkPoolNameQueuesFilterMutationResult = Awaited<ReturnType<typeof WorkPoolsService.postWorkPoolsByWorkPoolNameQueuesFilter>>;
export type WorkPoolsServicePostWorkPoolsByWorkPoolNameWorkersHeartbeatMutationResult = Awaited<ReturnType<typeof WorkPoolsService.postWorkPoolsByWorkPoolNameWorkersHeartbeat>>;
export type WorkPoolsServicePostWorkPoolsByWorkPoolNameWorkersFilterMutationResult = Awaited<ReturnType<typeof WorkPoolsService.postWorkPoolsByWorkPoolNameWorkersFilter>>;
export type TaskWorkersServicePostTaskWorkersFilterMutationResult = Awaited<ReturnType<typeof TaskWorkersService.postTaskWorkersFilter>>;
export type WorkQueuesServicePostWorkQueuesMutationResult = Awaited<ReturnType<typeof WorkQueuesService.postWorkQueues>>;
export type WorkQueuesServicePostWorkQueuesByIdGetRunsMutationResult = Awaited<ReturnType<typeof WorkQueuesService.postWorkQueuesByIdGetRuns>>;
export type WorkQueuesServicePostWorkQueuesFilterMutationResult = Awaited<ReturnType<typeof WorkQueuesService.postWorkQueuesFilter>>;
export type ArtifactsServicePostArtifactsMutationResult = Awaited<ReturnType<typeof ArtifactsService.postArtifacts>>;
export type ArtifactsServicePostArtifactsFilterMutationResult = Awaited<ReturnType<typeof ArtifactsService.postArtifactsFilter>>;
export type ArtifactsServicePostArtifactsLatestFilterMutationResult = Awaited<ReturnType<typeof ArtifactsService.postArtifactsLatestFilter>>;
export type ArtifactsServicePostArtifactsCountMutationResult = Awaited<ReturnType<typeof ArtifactsService.postArtifactsCount>>;
export type ArtifactsServicePostArtifactsLatestCountMutationResult = Awaited<ReturnType<typeof ArtifactsService.postArtifactsLatestCount>>;
export type BlockSchemasServicePostBlockSchemasMutationResult = Awaited<ReturnType<typeof BlockSchemasService.postBlockSchemas>>;
export type BlockSchemasServicePostBlockSchemasFilterMutationResult = Awaited<ReturnType<typeof BlockSchemasService.postBlockSchemasFilter>>;
export type VariablesServicePostVariablesMutationResult = Awaited<ReturnType<typeof VariablesService.postVariables>>;
export type VariablesServicePostVariablesFilterMutationResult = Awaited<ReturnType<typeof VariablesService.postVariablesFilter>>;
export type VariablesServicePostVariablesCountMutationResult = Awaited<ReturnType<typeof VariablesService.postVariablesCount>>;
export type EventsServicePostEventsMutationResult = Awaited<ReturnType<typeof EventsService.postEvents>>;
export type EventsServicePostEventsFilterMutationResult = Awaited<ReturnType<typeof EventsService.postEventsFilter>>;
export type EventsServicePostEventsCountByByCountableMutationResult = Awaited<ReturnType<typeof EventsService.postEventsCountByByCountable>>;
export type AutomationsServicePostAutomationsMutationResult = Awaited<ReturnType<typeof AutomationsService.postAutomations>>;
export type AutomationsServicePostAutomationsFilterMutationResult = Awaited<ReturnType<typeof AutomationsService.postAutomationsFilter>>;
export type AutomationsServicePostAutomationsCountMutationResult = Awaited<ReturnType<typeof AutomationsService.postAutomationsCount>>;
export type AutomationsServicePostTemplatesValidateMutationResult = Awaited<ReturnType<typeof AutomationsService.postTemplatesValidate>>;
export type UiServicePostUiFlowsCountDeploymentsMutationResult = Awaited<ReturnType<typeof UiService.postUiFlowsCountDeployments>>;
export type UiServicePostUiFlowsNextRunsMutationResult = Awaited<ReturnType<typeof UiService.postUiFlowsNextRuns>>;
export type UiServicePostUiFlowRunsHistoryMutationResult = Awaited<ReturnType<typeof UiService.postUiFlowRunsHistory>>;
export type UiServicePostUiFlowRunsCountTaskRunsMutationResult = Awaited<ReturnType<typeof UiService.postUiFlowRunsCountTaskRuns>>;
export type UiServicePostUiSchemasValidateMutationResult = Awaited<ReturnType<typeof UiService.postUiSchemasValidate>>;
export type UiServicePostUiTaskRunsDashboardCountsMutationResult = Awaited<ReturnType<typeof UiService.postUiTaskRunsDashboardCounts>>;
export type UiServicePostUiTaskRunsCountMutationResult = Awaited<ReturnType<typeof UiService.postUiTaskRunsCount>>;
export type SchemasServicePostUiSchemasValidateMutationResult = Awaited<ReturnType<typeof SchemasService.postUiSchemasValidate>>;
export type AdminServicePostAdminDatabaseClearMutationResult = Awaited<ReturnType<typeof AdminService.postAdminDatabaseClear>>;
export type AdminServicePostAdminDatabaseDropMutationResult = Awaited<ReturnType<typeof AdminService.postAdminDatabaseDrop>>;
export type AdminServicePostAdminDatabaseCreateMutationResult = Awaited<ReturnType<typeof AdminService.postAdminDatabaseCreate>>;
export type SavedSearchesServicePutSavedSearchesMutationResult = Awaited<ReturnType<typeof SavedSearchesService.putSavedSearches>>;
export type AutomationsServicePutAutomationsByIdMutationResult = Awaited<ReturnType<typeof AutomationsService.putAutomationsById>>;
export type FlowsServicePatchFlowsByIdMutationResult = Awaited<ReturnType<typeof FlowsService.patchFlowsById>>;
export type FlowRunsServicePatchFlowRunsByIdMutationResult = Awaited<ReturnType<typeof FlowRunsService.patchFlowRunsById>>;
export type FlowRunsServicePatchFlowRunsByIdLabelsMutationResult = Awaited<ReturnType<typeof FlowRunsService.patchFlowRunsByIdLabels>>;
export type TaskRunsServicePatchTaskRunsByIdMutationResult = Awaited<ReturnType<typeof TaskRunsService.patchTaskRunsById>>;
export type FlowRunNotificationPoliciesServicePatchFlowRunNotificationPoliciesByIdMutationResult = Awaited<ReturnType<typeof FlowRunNotificationPoliciesService.patchFlowRunNotificationPoliciesById>>;
export type DeploymentsServicePatchDeploymentsByIdMutationResult = Awaited<ReturnType<typeof DeploymentsService.patchDeploymentsById>>;
export type DeploymentsServicePatchDeploymentsByIdSchedulesByScheduleIdMutationResult = Awaited<ReturnType<typeof DeploymentsService.patchDeploymentsByIdSchedulesByScheduleId>>;
export type ConcurrencyLimitsV2ServicePatchV2ConcurrencyLimitsByIdOrNameMutationResult = Awaited<ReturnType<typeof ConcurrencyLimitsV2Service.patchV2ConcurrencyLimitsByIdOrName>>;
export type BlockTypesServicePatchBlockTypesByIdMutationResult = Awaited<ReturnType<typeof BlockTypesService.patchBlockTypesById>>;
export type BlockDocumentsServicePatchBlockDocumentsByIdMutationResult = Awaited<ReturnType<typeof BlockDocumentsService.patchBlockDocumentsById>>;
export type WorkPoolsServicePatchWorkPoolsByNameMutationResult = Awaited<ReturnType<typeof WorkPoolsService.patchWorkPoolsByName>>;
export type WorkPoolsServicePatchWorkPoolsByWorkPoolNameQueuesByNameMutationResult = Awaited<ReturnType<typeof WorkPoolsService.patchWorkPoolsByWorkPoolNameQueuesByName>>;
export type WorkQueuesServicePatchWorkQueuesByIdMutationResult = Awaited<ReturnType<typeof WorkQueuesService.patchWorkQueuesById>>;
export type ArtifactsServicePatchArtifactsByIdMutationResult = Awaited<ReturnType<typeof ArtifactsService.patchArtifactsById>>;
export type VariablesServicePatchVariablesByIdMutationResult = Awaited<ReturnType<typeof VariablesService.patchVariablesById>>;
export type VariablesServicePatchVariablesNameByNameMutationResult = Awaited<ReturnType<typeof VariablesService.patchVariablesNameByName>>;
export type AutomationsServicePatchAutomationsByIdMutationResult = Awaited<ReturnType<typeof AutomationsService.patchAutomationsById>>;
export type FlowsServiceDeleteFlowsByIdMutationResult = Awaited<ReturnType<typeof FlowsService.deleteFlowsById>>;
export type FlowRunsServiceDeleteFlowRunsByIdMutationResult = Awaited<ReturnType<typeof FlowRunsService.deleteFlowRunsById>>;
export type FlowRunsServiceDeleteFlowRunsByIdInputByKeyMutationResult = Awaited<ReturnType<typeof FlowRunsService.deleteFlowRunsByIdInputByKey>>;
export type TaskRunsServiceDeleteTaskRunsByIdMutationResult = Awaited<ReturnType<typeof TaskRunsService.deleteTaskRunsById>>;
export type FlowRunNotificationPoliciesServiceDeleteFlowRunNotificationPoliciesByIdMutationResult = Awaited<ReturnType<typeof FlowRunNotificationPoliciesService.deleteFlowRunNotificationPoliciesById>>;
export type DeploymentsServiceDeleteDeploymentsByIdMutationResult = Awaited<ReturnType<typeof DeploymentsService.deleteDeploymentsById>>;
export type DeploymentsServiceDeleteDeploymentsByIdSchedulesByScheduleIdMutationResult = Awaited<ReturnType<typeof DeploymentsService.deleteDeploymentsByIdSchedulesByScheduleId>>;
export type SavedSearchesServiceDeleteSavedSearchesByIdMutationResult = Awaited<ReturnType<typeof SavedSearchesService.deleteSavedSearchesById>>;
export type ConcurrencyLimitsServiceDeleteConcurrencyLimitsByIdMutationResult = Awaited<ReturnType<typeof ConcurrencyLimitsService.deleteConcurrencyLimitsById>>;
export type ConcurrencyLimitsServiceDeleteConcurrencyLimitsTagByTagMutationResult = Awaited<ReturnType<typeof ConcurrencyLimitsService.deleteConcurrencyLimitsTagByTag>>;
export type ConcurrencyLimitsV2ServiceDeleteV2ConcurrencyLimitsByIdOrNameMutationResult = Awaited<ReturnType<typeof ConcurrencyLimitsV2Service.deleteV2ConcurrencyLimitsByIdOrName>>;
export type BlockTypesServiceDeleteBlockTypesByIdMutationResult = Awaited<ReturnType<typeof BlockTypesService.deleteBlockTypesById>>;
export type BlockDocumentsServiceDeleteBlockDocumentsByIdMutationResult = Awaited<ReturnType<typeof BlockDocumentsService.deleteBlockDocumentsById>>;
export type WorkPoolsServiceDeleteWorkPoolsByNameMutationResult = Awaited<ReturnType<typeof WorkPoolsService.deleteWorkPoolsByName>>;
export type WorkPoolsServiceDeleteWorkPoolsByWorkPoolNameQueuesByNameMutationResult = Awaited<ReturnType<typeof WorkPoolsService.deleteWorkPoolsByWorkPoolNameQueuesByName>>;
export type WorkPoolsServiceDeleteWorkPoolsByWorkPoolNameWorkersByNameMutationResult = Awaited<ReturnType<typeof WorkPoolsService.deleteWorkPoolsByWorkPoolNameWorkersByName>>;
export type WorkQueuesServiceDeleteWorkQueuesByIdMutationResult = Awaited<ReturnType<typeof WorkQueuesService.deleteWorkQueuesById>>;
export type ArtifactsServiceDeleteArtifactsByIdMutationResult = Awaited<ReturnType<typeof ArtifactsService.deleteArtifactsById>>;
export type BlockSchemasServiceDeleteBlockSchemasByIdMutationResult = Awaited<ReturnType<typeof BlockSchemasService.deleteBlockSchemasById>>;
export type VariablesServiceDeleteVariablesByIdMutationResult = Awaited<ReturnType<typeof VariablesService.deleteVariablesById>>;
export type VariablesServiceDeleteVariablesNameByNameMutationResult = Awaited<ReturnType<typeof VariablesService.deleteVariablesNameByName>>;
export type AutomationsServiceDeleteAutomationsByIdMutationResult = Awaited<ReturnType<typeof AutomationsService.deleteAutomationsById>>;
export type AutomationsServiceDeleteAutomationsOwnedByByResourceIdMutationResult = Awaited<ReturnType<typeof AutomationsService.deleteAutomationsOwnedByByResourceId>>;
