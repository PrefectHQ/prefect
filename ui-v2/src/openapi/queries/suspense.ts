// generated with @7nohe/openapi-react-query-codegen@1.6.2 

import { UseQueryOptions, useSuspenseQuery } from "@tanstack/react-query";
import { AdminService, ArtifactsService, AutomationsService, BlockCapabilitiesService, BlockDocumentsService, BlockSchemasService, BlockTypesService, CollectionsService, ConcurrencyLimitsService, ConcurrencyLimitsV2Service, DefaultService, DeploymentsService, EventsService, FlowRunNotificationPoliciesService, FlowRunStatesService, FlowRunsService, FlowsService, RootService, SavedSearchesService, TaskRunStatesService, TaskRunsService, VariablesService, WorkPoolsService, WorkQueuesService } from "../requests/services.gen";
import * as Common from "./common";
export const useRootServiceGetHealthSuspense = <TData = Common.RootServiceGetHealthDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>(queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useSuspenseQuery<TData, TError>({ queryKey: Common.UseRootServiceGetHealthKeyFn(queryKey), queryFn: () => RootService.getHealth() as TData, ...options });
export const useRootServiceGetVersionSuspense = <TData = Common.RootServiceGetVersionDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>(queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useSuspenseQuery<TData, TError>({ queryKey: Common.UseRootServiceGetVersionKeyFn(queryKey), queryFn: () => RootService.getVersion() as TData, ...options });
export const useRootServiceGetHelloSuspense = <TData = Common.RootServiceGetHelloDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ xPrefectApiVersion }: {
  xPrefectApiVersion?: string;
} = {}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useSuspenseQuery<TData, TError>({ queryKey: Common.UseRootServiceGetHelloKeyFn({ xPrefectApiVersion }, queryKey), queryFn: () => RootService.getHello({ xPrefectApiVersion }) as TData, ...options });
export const useRootServiceGetReadySuspense = <TData = Common.RootServiceGetReadyDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ xPrefectApiVersion }: {
  xPrefectApiVersion?: string;
} = {}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useSuspenseQuery<TData, TError>({ queryKey: Common.UseRootServiceGetReadyKeyFn({ xPrefectApiVersion }, queryKey), queryFn: () => RootService.getReady({ xPrefectApiVersion }) as TData, ...options });
export const useFlowsServiceGetFlowsByIdSuspense = <TData = Common.FlowsServiceGetFlowsByIdDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useSuspenseQuery<TData, TError>({ queryKey: Common.UseFlowsServiceGetFlowsByIdKeyFn({ id, xPrefectApiVersion }, queryKey), queryFn: () => FlowsService.getFlowsById({ id, xPrefectApiVersion }) as TData, ...options });
export const useFlowsServiceGetFlowsNameByNameSuspense = <TData = Common.FlowsServiceGetFlowsNameByNameDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ name, xPrefectApiVersion }: {
  name: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useSuspenseQuery<TData, TError>({ queryKey: Common.UseFlowsServiceGetFlowsNameByNameKeyFn({ name, xPrefectApiVersion }, queryKey), queryFn: () => FlowsService.getFlowsNameByName({ name, xPrefectApiVersion }) as TData, ...options });
export const useFlowRunsServiceGetFlowRunsByIdSuspense = <TData = Common.FlowRunsServiceGetFlowRunsByIdDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useSuspenseQuery<TData, TError>({ queryKey: Common.UseFlowRunsServiceGetFlowRunsByIdKeyFn({ id, xPrefectApiVersion }, queryKey), queryFn: () => FlowRunsService.getFlowRunsById({ id, xPrefectApiVersion }) as TData, ...options });
export const useFlowRunsServiceGetFlowRunsByIdGraphSuspense = <TData = Common.FlowRunsServiceGetFlowRunsByIdGraphDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useSuspenseQuery<TData, TError>({ queryKey: Common.UseFlowRunsServiceGetFlowRunsByIdGraphKeyFn({ id, xPrefectApiVersion }, queryKey), queryFn: () => FlowRunsService.getFlowRunsByIdGraph({ id, xPrefectApiVersion }) as TData, ...options });
export const useFlowRunsServiceGetFlowRunsByIdGraphV2Suspense = <TData = Common.FlowRunsServiceGetFlowRunsByIdGraphV2DefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ id, since, xPrefectApiVersion }: {
  id: string;
  since?: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useSuspenseQuery<TData, TError>({ queryKey: Common.UseFlowRunsServiceGetFlowRunsByIdGraphV2KeyFn({ id, since, xPrefectApiVersion }, queryKey), queryFn: () => FlowRunsService.getFlowRunsByIdGraphV2({ id, since, xPrefectApiVersion }) as TData, ...options });
export const useFlowRunsServiceGetFlowRunsByIdInputByKeySuspense = <TData = Common.FlowRunsServiceGetFlowRunsByIdInputByKeyDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ id, key, xPrefectApiVersion }: {
  id: string;
  key: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useSuspenseQuery<TData, TError>({ queryKey: Common.UseFlowRunsServiceGetFlowRunsByIdInputByKeyKeyFn({ id, key, xPrefectApiVersion }, queryKey), queryFn: () => FlowRunsService.getFlowRunsByIdInputByKey({ id, key, xPrefectApiVersion }) as TData, ...options });
export const useFlowRunsServiceGetFlowRunsByIdLogsDownloadSuspense = <TData = Common.FlowRunsServiceGetFlowRunsByIdLogsDownloadDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useSuspenseQuery<TData, TError>({ queryKey: Common.UseFlowRunsServiceGetFlowRunsByIdLogsDownloadKeyFn({ id, xPrefectApiVersion }, queryKey), queryFn: () => FlowRunsService.getFlowRunsByIdLogsDownload({ id, xPrefectApiVersion }) as TData, ...options });
export const useTaskRunsServiceGetTaskRunsByIdSuspense = <TData = Common.TaskRunsServiceGetTaskRunsByIdDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useSuspenseQuery<TData, TError>({ queryKey: Common.UseTaskRunsServiceGetTaskRunsByIdKeyFn({ id, xPrefectApiVersion }, queryKey), queryFn: () => TaskRunsService.getTaskRunsById({ id, xPrefectApiVersion }) as TData, ...options });
export const useFlowRunStatesServiceGetFlowRunStatesByIdSuspense = <TData = Common.FlowRunStatesServiceGetFlowRunStatesByIdDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useSuspenseQuery<TData, TError>({ queryKey: Common.UseFlowRunStatesServiceGetFlowRunStatesByIdKeyFn({ id, xPrefectApiVersion }, queryKey), queryFn: () => FlowRunStatesService.getFlowRunStatesById({ id, xPrefectApiVersion }) as TData, ...options });
export const useFlowRunStatesServiceGetFlowRunStatesSuspense = <TData = Common.FlowRunStatesServiceGetFlowRunStatesDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ flowRunId, xPrefectApiVersion }: {
  flowRunId: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useSuspenseQuery<TData, TError>({ queryKey: Common.UseFlowRunStatesServiceGetFlowRunStatesKeyFn({ flowRunId, xPrefectApiVersion }, queryKey), queryFn: () => FlowRunStatesService.getFlowRunStates({ flowRunId, xPrefectApiVersion }) as TData, ...options });
export const useTaskRunStatesServiceGetTaskRunStatesByIdSuspense = <TData = Common.TaskRunStatesServiceGetTaskRunStatesByIdDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useSuspenseQuery<TData, TError>({ queryKey: Common.UseTaskRunStatesServiceGetTaskRunStatesByIdKeyFn({ id, xPrefectApiVersion }, queryKey), queryFn: () => TaskRunStatesService.getTaskRunStatesById({ id, xPrefectApiVersion }) as TData, ...options });
export const useTaskRunStatesServiceGetTaskRunStatesSuspense = <TData = Common.TaskRunStatesServiceGetTaskRunStatesDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ taskRunId, xPrefectApiVersion }: {
  taskRunId: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useSuspenseQuery<TData, TError>({ queryKey: Common.UseTaskRunStatesServiceGetTaskRunStatesKeyFn({ taskRunId, xPrefectApiVersion }, queryKey), queryFn: () => TaskRunStatesService.getTaskRunStates({ taskRunId, xPrefectApiVersion }) as TData, ...options });
export const useFlowRunNotificationPoliciesServiceGetFlowRunNotificationPoliciesByIdSuspense = <TData = Common.FlowRunNotificationPoliciesServiceGetFlowRunNotificationPoliciesByIdDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useSuspenseQuery<TData, TError>({ queryKey: Common.UseFlowRunNotificationPoliciesServiceGetFlowRunNotificationPoliciesByIdKeyFn({ id, xPrefectApiVersion }, queryKey), queryFn: () => FlowRunNotificationPoliciesService.getFlowRunNotificationPoliciesById({ id, xPrefectApiVersion }) as TData, ...options });
export const useDeploymentsServiceGetDeploymentsByIdSuspense = <TData = Common.DeploymentsServiceGetDeploymentsByIdDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useSuspenseQuery<TData, TError>({ queryKey: Common.UseDeploymentsServiceGetDeploymentsByIdKeyFn({ id, xPrefectApiVersion }, queryKey), queryFn: () => DeploymentsService.getDeploymentsById({ id, xPrefectApiVersion }) as TData, ...options });
export const useDeploymentsServiceGetDeploymentsNameByFlowNameByDeploymentNameSuspense = <TData = Common.DeploymentsServiceGetDeploymentsNameByFlowNameByDeploymentNameDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ deploymentName, flowName, xPrefectApiVersion }: {
  deploymentName: string;
  flowName: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useSuspenseQuery<TData, TError>({ queryKey: Common.UseDeploymentsServiceGetDeploymentsNameByFlowNameByDeploymentNameKeyFn({ deploymentName, flowName, xPrefectApiVersion }, queryKey), queryFn: () => DeploymentsService.getDeploymentsNameByFlowNameByDeploymentName({ deploymentName, flowName, xPrefectApiVersion }) as TData, ...options });
export const useDeploymentsServiceGetDeploymentsByIdWorkQueueCheckSuspense = <TData = Common.DeploymentsServiceGetDeploymentsByIdWorkQueueCheckDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useSuspenseQuery<TData, TError>({ queryKey: Common.UseDeploymentsServiceGetDeploymentsByIdWorkQueueCheckKeyFn({ id, xPrefectApiVersion }, queryKey), queryFn: () => DeploymentsService.getDeploymentsByIdWorkQueueCheck({ id, xPrefectApiVersion }) as TData, ...options });
export const useDeploymentsServiceGetDeploymentsByIdSchedulesSuspense = <TData = Common.DeploymentsServiceGetDeploymentsByIdSchedulesDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useSuspenseQuery<TData, TError>({ queryKey: Common.UseDeploymentsServiceGetDeploymentsByIdSchedulesKeyFn({ id, xPrefectApiVersion }, queryKey), queryFn: () => DeploymentsService.getDeploymentsByIdSchedules({ id, xPrefectApiVersion }) as TData, ...options });
export const useSavedSearchesServiceGetSavedSearchesByIdSuspense = <TData = Common.SavedSearchesServiceGetSavedSearchesByIdDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useSuspenseQuery<TData, TError>({ queryKey: Common.UseSavedSearchesServiceGetSavedSearchesByIdKeyFn({ id, xPrefectApiVersion }, queryKey), queryFn: () => SavedSearchesService.getSavedSearchesById({ id, xPrefectApiVersion }) as TData, ...options });
export const useConcurrencyLimitsServiceGetConcurrencyLimitsByIdSuspense = <TData = Common.ConcurrencyLimitsServiceGetConcurrencyLimitsByIdDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useSuspenseQuery<TData, TError>({ queryKey: Common.UseConcurrencyLimitsServiceGetConcurrencyLimitsByIdKeyFn({ id, xPrefectApiVersion }, queryKey), queryFn: () => ConcurrencyLimitsService.getConcurrencyLimitsById({ id, xPrefectApiVersion }) as TData, ...options });
export const useConcurrencyLimitsServiceGetConcurrencyLimitsTagByTagSuspense = <TData = Common.ConcurrencyLimitsServiceGetConcurrencyLimitsTagByTagDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ tag, xPrefectApiVersion }: {
  tag: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useSuspenseQuery<TData, TError>({ queryKey: Common.UseConcurrencyLimitsServiceGetConcurrencyLimitsTagByTagKeyFn({ tag, xPrefectApiVersion }, queryKey), queryFn: () => ConcurrencyLimitsService.getConcurrencyLimitsTagByTag({ tag, xPrefectApiVersion }) as TData, ...options });
export const useConcurrencyLimitsV2ServiceGetV2ConcurrencyLimitsByIdOrNameSuspense = <TData = Common.ConcurrencyLimitsV2ServiceGetV2ConcurrencyLimitsByIdOrNameDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ idOrName, xPrefectApiVersion }: {
  idOrName: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useSuspenseQuery<TData, TError>({ queryKey: Common.UseConcurrencyLimitsV2ServiceGetV2ConcurrencyLimitsByIdOrNameKeyFn({ idOrName, xPrefectApiVersion }, queryKey), queryFn: () => ConcurrencyLimitsV2Service.getV2ConcurrencyLimitsByIdOrName({ idOrName, xPrefectApiVersion }) as TData, ...options });
export const useBlockTypesServiceGetBlockTypesByIdSuspense = <TData = Common.BlockTypesServiceGetBlockTypesByIdDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useSuspenseQuery<TData, TError>({ queryKey: Common.UseBlockTypesServiceGetBlockTypesByIdKeyFn({ id, xPrefectApiVersion }, queryKey), queryFn: () => BlockTypesService.getBlockTypesById({ id, xPrefectApiVersion }) as TData, ...options });
export const useBlockTypesServiceGetBlockTypesSlugBySlugSuspense = <TData = Common.BlockTypesServiceGetBlockTypesSlugBySlugDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ slug, xPrefectApiVersion }: {
  slug: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useSuspenseQuery<TData, TError>({ queryKey: Common.UseBlockTypesServiceGetBlockTypesSlugBySlugKeyFn({ slug, xPrefectApiVersion }, queryKey), queryFn: () => BlockTypesService.getBlockTypesSlugBySlug({ slug, xPrefectApiVersion }) as TData, ...options });
export const useBlockTypesServiceGetBlockTypesSlugBySlugBlockDocumentsSuspense = <TData = Common.BlockTypesServiceGetBlockTypesSlugBySlugBlockDocumentsDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ includeSecrets, slug, xPrefectApiVersion }: {
  includeSecrets?: boolean;
  slug: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useSuspenseQuery<TData, TError>({ queryKey: Common.UseBlockTypesServiceGetBlockTypesSlugBySlugBlockDocumentsKeyFn({ includeSecrets, slug, xPrefectApiVersion }, queryKey), queryFn: () => BlockTypesService.getBlockTypesSlugBySlugBlockDocuments({ includeSecrets, slug, xPrefectApiVersion }) as TData, ...options });
export const useBlockTypesServiceGetBlockTypesSlugBySlugBlockDocumentsNameByBlockDocumentNameSuspense = <TData = Common.BlockTypesServiceGetBlockTypesSlugBySlugBlockDocumentsNameByBlockDocumentNameDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ blockDocumentName, includeSecrets, slug, xPrefectApiVersion }: {
  blockDocumentName: string;
  includeSecrets?: boolean;
  slug: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useSuspenseQuery<TData, TError>({ queryKey: Common.UseBlockTypesServiceGetBlockTypesSlugBySlugBlockDocumentsNameByBlockDocumentNameKeyFn({ blockDocumentName, includeSecrets, slug, xPrefectApiVersion }, queryKey), queryFn: () => BlockTypesService.getBlockTypesSlugBySlugBlockDocumentsNameByBlockDocumentName({ blockDocumentName, includeSecrets, slug, xPrefectApiVersion }) as TData, ...options });
export const useBlockDocumentsServiceGetBlockTypesSlugBySlugBlockDocumentsSuspense = <TData = Common.BlockDocumentsServiceGetBlockTypesSlugBySlugBlockDocumentsDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ includeSecrets, slug, xPrefectApiVersion }: {
  includeSecrets?: boolean;
  slug: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useSuspenseQuery<TData, TError>({ queryKey: Common.UseBlockDocumentsServiceGetBlockTypesSlugBySlugBlockDocumentsKeyFn({ includeSecrets, slug, xPrefectApiVersion }, queryKey), queryFn: () => BlockDocumentsService.getBlockTypesSlugBySlugBlockDocuments({ includeSecrets, slug, xPrefectApiVersion }) as TData, ...options });
export const useBlockDocumentsServiceGetBlockTypesSlugBySlugBlockDocumentsNameByBlockDocumentNameSuspense = <TData = Common.BlockDocumentsServiceGetBlockTypesSlugBySlugBlockDocumentsNameByBlockDocumentNameDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ blockDocumentName, includeSecrets, slug, xPrefectApiVersion }: {
  blockDocumentName: string;
  includeSecrets?: boolean;
  slug: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useSuspenseQuery<TData, TError>({ queryKey: Common.UseBlockDocumentsServiceGetBlockTypesSlugBySlugBlockDocumentsNameByBlockDocumentNameKeyFn({ blockDocumentName, includeSecrets, slug, xPrefectApiVersion }, queryKey), queryFn: () => BlockDocumentsService.getBlockTypesSlugBySlugBlockDocumentsNameByBlockDocumentName({ blockDocumentName, includeSecrets, slug, xPrefectApiVersion }) as TData, ...options });
export const useBlockDocumentsServiceGetBlockDocumentsByIdSuspense = <TData = Common.BlockDocumentsServiceGetBlockDocumentsByIdDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ id, includeSecrets, xPrefectApiVersion }: {
  id: string;
  includeSecrets?: boolean;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useSuspenseQuery<TData, TError>({ queryKey: Common.UseBlockDocumentsServiceGetBlockDocumentsByIdKeyFn({ id, includeSecrets, xPrefectApiVersion }, queryKey), queryFn: () => BlockDocumentsService.getBlockDocumentsById({ id, includeSecrets, xPrefectApiVersion }) as TData, ...options });
export const useWorkPoolsServiceGetWorkPoolsByNameSuspense = <TData = Common.WorkPoolsServiceGetWorkPoolsByNameDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ name, xPrefectApiVersion }: {
  name: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useSuspenseQuery<TData, TError>({ queryKey: Common.UseWorkPoolsServiceGetWorkPoolsByNameKeyFn({ name, xPrefectApiVersion }, queryKey), queryFn: () => WorkPoolsService.getWorkPoolsByName({ name, xPrefectApiVersion }) as TData, ...options });
export const useWorkPoolsServiceGetWorkPoolsByWorkPoolNameQueuesByNameSuspense = <TData = Common.WorkPoolsServiceGetWorkPoolsByWorkPoolNameQueuesByNameDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ name, workPoolName, xPrefectApiVersion }: {
  name: string;
  workPoolName: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useSuspenseQuery<TData, TError>({ queryKey: Common.UseWorkPoolsServiceGetWorkPoolsByWorkPoolNameQueuesByNameKeyFn({ name, workPoolName, xPrefectApiVersion }, queryKey), queryFn: () => WorkPoolsService.getWorkPoolsByWorkPoolNameQueuesByName({ name, workPoolName, xPrefectApiVersion }) as TData, ...options });
export const useWorkQueuesServiceGetWorkQueuesByIdSuspense = <TData = Common.WorkQueuesServiceGetWorkQueuesByIdDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useSuspenseQuery<TData, TError>({ queryKey: Common.UseWorkQueuesServiceGetWorkQueuesByIdKeyFn({ id, xPrefectApiVersion }, queryKey), queryFn: () => WorkQueuesService.getWorkQueuesById({ id, xPrefectApiVersion }) as TData, ...options });
export const useWorkQueuesServiceGetWorkQueuesNameByNameSuspense = <TData = Common.WorkQueuesServiceGetWorkQueuesNameByNameDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ name, xPrefectApiVersion }: {
  name: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useSuspenseQuery<TData, TError>({ queryKey: Common.UseWorkQueuesServiceGetWorkQueuesNameByNameKeyFn({ name, xPrefectApiVersion }, queryKey), queryFn: () => WorkQueuesService.getWorkQueuesNameByName({ name, xPrefectApiVersion }) as TData, ...options });
export const useWorkQueuesServiceGetWorkQueuesByIdStatusSuspense = <TData = Common.WorkQueuesServiceGetWorkQueuesByIdStatusDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useSuspenseQuery<TData, TError>({ queryKey: Common.UseWorkQueuesServiceGetWorkQueuesByIdStatusKeyFn({ id, xPrefectApiVersion }, queryKey), queryFn: () => WorkQueuesService.getWorkQueuesByIdStatus({ id, xPrefectApiVersion }) as TData, ...options });
export const useArtifactsServiceGetArtifactsByIdSuspense = <TData = Common.ArtifactsServiceGetArtifactsByIdDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useSuspenseQuery<TData, TError>({ queryKey: Common.UseArtifactsServiceGetArtifactsByIdKeyFn({ id, xPrefectApiVersion }, queryKey), queryFn: () => ArtifactsService.getArtifactsById({ id, xPrefectApiVersion }) as TData, ...options });
export const useArtifactsServiceGetArtifactsByKeyLatestSuspense = <TData = Common.ArtifactsServiceGetArtifactsByKeyLatestDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ key, xPrefectApiVersion }: {
  key: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useSuspenseQuery<TData, TError>({ queryKey: Common.UseArtifactsServiceGetArtifactsByKeyLatestKeyFn({ key, xPrefectApiVersion }, queryKey), queryFn: () => ArtifactsService.getArtifactsByKeyLatest({ key, xPrefectApiVersion }) as TData, ...options });
export const useBlockSchemasServiceGetBlockSchemasByIdSuspense = <TData = Common.BlockSchemasServiceGetBlockSchemasByIdDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useSuspenseQuery<TData, TError>({ queryKey: Common.UseBlockSchemasServiceGetBlockSchemasByIdKeyFn({ id, xPrefectApiVersion }, queryKey), queryFn: () => BlockSchemasService.getBlockSchemasById({ id, xPrefectApiVersion }) as TData, ...options });
export const useBlockSchemasServiceGetBlockSchemasChecksumByChecksumSuspense = <TData = Common.BlockSchemasServiceGetBlockSchemasChecksumByChecksumDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ checksum, version, xPrefectApiVersion }: {
  checksum: string;
  version?: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useSuspenseQuery<TData, TError>({ queryKey: Common.UseBlockSchemasServiceGetBlockSchemasChecksumByChecksumKeyFn({ checksum, version, xPrefectApiVersion }, queryKey), queryFn: () => BlockSchemasService.getBlockSchemasChecksumByChecksum({ checksum, version, xPrefectApiVersion }) as TData, ...options });
export const useBlockCapabilitiesServiceGetBlockCapabilitiesSuspense = <TData = Common.BlockCapabilitiesServiceGetBlockCapabilitiesDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ xPrefectApiVersion }: {
  xPrefectApiVersion?: string;
} = {}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useSuspenseQuery<TData, TError>({ queryKey: Common.UseBlockCapabilitiesServiceGetBlockCapabilitiesKeyFn({ xPrefectApiVersion }, queryKey), queryFn: () => BlockCapabilitiesService.getBlockCapabilities({ xPrefectApiVersion }) as TData, ...options });
export const useCollectionsServiceGetCollectionsViewsByViewSuspense = <TData = Common.CollectionsServiceGetCollectionsViewsByViewDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ view, xPrefectApiVersion }: {
  view: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useSuspenseQuery<TData, TError>({ queryKey: Common.UseCollectionsServiceGetCollectionsViewsByViewKeyFn({ view, xPrefectApiVersion }, queryKey), queryFn: () => CollectionsService.getCollectionsViewsByView({ view, xPrefectApiVersion }) as TData, ...options });
export const useVariablesServiceGetVariablesByIdSuspense = <TData = Common.VariablesServiceGetVariablesByIdDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useSuspenseQuery<TData, TError>({ queryKey: Common.UseVariablesServiceGetVariablesByIdKeyFn({ id, xPrefectApiVersion }, queryKey), queryFn: () => VariablesService.getVariablesById({ id, xPrefectApiVersion }) as TData, ...options });
export const useVariablesServiceGetVariablesNameByNameSuspense = <TData = Common.VariablesServiceGetVariablesNameByNameDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ name, xPrefectApiVersion }: {
  name: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useSuspenseQuery<TData, TError>({ queryKey: Common.UseVariablesServiceGetVariablesNameByNameKeyFn({ name, xPrefectApiVersion }, queryKey), queryFn: () => VariablesService.getVariablesNameByName({ name, xPrefectApiVersion }) as TData, ...options });
export const useDefaultServiceGetCsrfTokenSuspense = <TData = Common.DefaultServiceGetCsrfTokenDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ client, xPrefectApiVersion }: {
  client: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useSuspenseQuery<TData, TError>({ queryKey: Common.UseDefaultServiceGetCsrfTokenKeyFn({ client, xPrefectApiVersion }, queryKey), queryFn: () => DefaultService.getCsrfToken({ client, xPrefectApiVersion }) as TData, ...options });
export const useEventsServiceGetEventsFilterNextSuspense = <TData = Common.EventsServiceGetEventsFilterNextDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ pageToken, xPrefectApiVersion }: {
  pageToken: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useSuspenseQuery<TData, TError>({ queryKey: Common.UseEventsServiceGetEventsFilterNextKeyFn({ pageToken, xPrefectApiVersion }, queryKey), queryFn: () => EventsService.getEventsFilterNext({ pageToken, xPrefectApiVersion }) as TData, ...options });
export const useAutomationsServiceGetAutomationsByIdSuspense = <TData = Common.AutomationsServiceGetAutomationsByIdDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useSuspenseQuery<TData, TError>({ queryKey: Common.UseAutomationsServiceGetAutomationsByIdKeyFn({ id, xPrefectApiVersion }, queryKey), queryFn: () => AutomationsService.getAutomationsById({ id, xPrefectApiVersion }) as TData, ...options });
export const useAutomationsServiceGetAutomationsRelatedToByResourceIdSuspense = <TData = Common.AutomationsServiceGetAutomationsRelatedToByResourceIdDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ resourceId, xPrefectApiVersion }: {
  resourceId: string;
  xPrefectApiVersion?: string;
}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useSuspenseQuery<TData, TError>({ queryKey: Common.UseAutomationsServiceGetAutomationsRelatedToByResourceIdKeyFn({ resourceId, xPrefectApiVersion }, queryKey), queryFn: () => AutomationsService.getAutomationsRelatedToByResourceId({ resourceId, xPrefectApiVersion }) as TData, ...options });
export const useAdminServiceGetAdminSettingsSuspense = <TData = Common.AdminServiceGetAdminSettingsDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ xPrefectApiVersion }: {
  xPrefectApiVersion?: string;
} = {}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useSuspenseQuery<TData, TError>({ queryKey: Common.UseAdminServiceGetAdminSettingsKeyFn({ xPrefectApiVersion }, queryKey), queryFn: () => AdminService.getAdminSettings({ xPrefectApiVersion }) as TData, ...options });
export const useAdminServiceGetAdminVersionSuspense = <TData = Common.AdminServiceGetAdminVersionDefaultResponse, TError = unknown, TQueryKey extends Array<unknown> = unknown[]>({ xPrefectApiVersion }: {
  xPrefectApiVersion?: string;
} = {}, queryKey?: TQueryKey, options?: Omit<UseQueryOptions<TData, TError>, "queryKey" | "queryFn">) => useSuspenseQuery<TData, TError>({ queryKey: Common.UseAdminServiceGetAdminVersionKeyFn({ xPrefectApiVersion }, queryKey), queryFn: () => AdminService.getAdminVersion({ xPrefectApiVersion }) as TData, ...options });
