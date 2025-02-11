// generated with @7nohe/openapi-react-query-codegen@1.6.2 

import { type QueryClient } from "@tanstack/react-query";
import { AdminService, ArtifactsService, AutomationsService, BlockCapabilitiesService, BlockDocumentsService, BlockSchemasService, BlockTypesService, CollectionsService, ConcurrencyLimitsService, ConcurrencyLimitsV2Service, DefaultService, DeploymentsService, EventsService, FlowRunNotificationPoliciesService, FlowRunStatesService, FlowRunsService, FlowsService, RootService, SavedSearchesService, TaskRunStatesService, TaskRunsService, VariablesService, WorkPoolsService, WorkQueuesService } from "../requests/services.gen";
import * as Common from "./common";
export const prefetchUseRootServiceGetHealth = (queryClient: QueryClient) => queryClient.prefetchQuery({ queryKey: Common.UseRootServiceGetHealthKeyFn(), queryFn: () => RootService.getHealth() });
export const prefetchUseRootServiceGetVersion = (queryClient: QueryClient) => queryClient.prefetchQuery({ queryKey: Common.UseRootServiceGetVersionKeyFn(), queryFn: () => RootService.getVersion() });
export const prefetchUseRootServiceGetHello = (queryClient: QueryClient, { xPrefectApiVersion }: {
  xPrefectApiVersion?: string;
} = {}) => queryClient.prefetchQuery({ queryKey: Common.UseRootServiceGetHelloKeyFn({ xPrefectApiVersion }), queryFn: () => RootService.getHello({ xPrefectApiVersion }) });
export const prefetchUseRootServiceGetReady = (queryClient: QueryClient, { xPrefectApiVersion }: {
  xPrefectApiVersion?: string;
} = {}) => queryClient.prefetchQuery({ queryKey: Common.UseRootServiceGetReadyKeyFn({ xPrefectApiVersion }), queryFn: () => RootService.getReady({ xPrefectApiVersion }) });
export const prefetchUseFlowsServiceGetFlowsById = (queryClient: QueryClient, { id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}) => queryClient.prefetchQuery({ queryKey: Common.UseFlowsServiceGetFlowsByIdKeyFn({ id, xPrefectApiVersion }), queryFn: () => FlowsService.getFlowsById({ id, xPrefectApiVersion }) });
export const prefetchUseFlowsServiceGetFlowsNameByName = (queryClient: QueryClient, { name, xPrefectApiVersion }: {
  name: string;
  xPrefectApiVersion?: string;
}) => queryClient.prefetchQuery({ queryKey: Common.UseFlowsServiceGetFlowsNameByNameKeyFn({ name, xPrefectApiVersion }), queryFn: () => FlowsService.getFlowsNameByName({ name, xPrefectApiVersion }) });
export const prefetchUseFlowRunsServiceGetFlowRunsById = (queryClient: QueryClient, { id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}) => queryClient.prefetchQuery({ queryKey: Common.UseFlowRunsServiceGetFlowRunsByIdKeyFn({ id, xPrefectApiVersion }), queryFn: () => FlowRunsService.getFlowRunsById({ id, xPrefectApiVersion }) });
export const prefetchUseFlowRunsServiceGetFlowRunsByIdGraph = (queryClient: QueryClient, { id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}) => queryClient.prefetchQuery({ queryKey: Common.UseFlowRunsServiceGetFlowRunsByIdGraphKeyFn({ id, xPrefectApiVersion }), queryFn: () => FlowRunsService.getFlowRunsByIdGraph({ id, xPrefectApiVersion }) });
export const prefetchUseFlowRunsServiceGetFlowRunsByIdGraphV2 = (queryClient: QueryClient, { id, since, xPrefectApiVersion }: {
  id: string;
  since?: string;
  xPrefectApiVersion?: string;
}) => queryClient.prefetchQuery({ queryKey: Common.UseFlowRunsServiceGetFlowRunsByIdGraphV2KeyFn({ id, since, xPrefectApiVersion }), queryFn: () => FlowRunsService.getFlowRunsByIdGraphV2({ id, since, xPrefectApiVersion }) });
export const prefetchUseFlowRunsServiceGetFlowRunsByIdInputByKey = (queryClient: QueryClient, { id, key, xPrefectApiVersion }: {
  id: string;
  key: string;
  xPrefectApiVersion?: string;
}) => queryClient.prefetchQuery({ queryKey: Common.UseFlowRunsServiceGetFlowRunsByIdInputByKeyKeyFn({ id, key, xPrefectApiVersion }), queryFn: () => FlowRunsService.getFlowRunsByIdInputByKey({ id, key, xPrefectApiVersion }) });
export const prefetchUseFlowRunsServiceGetFlowRunsByIdLogsDownload = (queryClient: QueryClient, { id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}) => queryClient.prefetchQuery({ queryKey: Common.UseFlowRunsServiceGetFlowRunsByIdLogsDownloadKeyFn({ id, xPrefectApiVersion }), queryFn: () => FlowRunsService.getFlowRunsByIdLogsDownload({ id, xPrefectApiVersion }) });
export const prefetchUseTaskRunsServiceGetTaskRunsById = (queryClient: QueryClient, { id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}) => queryClient.prefetchQuery({ queryKey: Common.UseTaskRunsServiceGetTaskRunsByIdKeyFn({ id, xPrefectApiVersion }), queryFn: () => TaskRunsService.getTaskRunsById({ id, xPrefectApiVersion }) });
export const prefetchUseFlowRunStatesServiceGetFlowRunStatesById = (queryClient: QueryClient, { id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}) => queryClient.prefetchQuery({ queryKey: Common.UseFlowRunStatesServiceGetFlowRunStatesByIdKeyFn({ id, xPrefectApiVersion }), queryFn: () => FlowRunStatesService.getFlowRunStatesById({ id, xPrefectApiVersion }) });
export const prefetchUseFlowRunStatesServiceGetFlowRunStates = (queryClient: QueryClient, { flowRunId, xPrefectApiVersion }: {
  flowRunId: string;
  xPrefectApiVersion?: string;
}) => queryClient.prefetchQuery({ queryKey: Common.UseFlowRunStatesServiceGetFlowRunStatesKeyFn({ flowRunId, xPrefectApiVersion }), queryFn: () => FlowRunStatesService.getFlowRunStates({ flowRunId, xPrefectApiVersion }) });
export const prefetchUseTaskRunStatesServiceGetTaskRunStatesById = (queryClient: QueryClient, { id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}) => queryClient.prefetchQuery({ queryKey: Common.UseTaskRunStatesServiceGetTaskRunStatesByIdKeyFn({ id, xPrefectApiVersion }), queryFn: () => TaskRunStatesService.getTaskRunStatesById({ id, xPrefectApiVersion }) });
export const prefetchUseTaskRunStatesServiceGetTaskRunStates = (queryClient: QueryClient, { taskRunId, xPrefectApiVersion }: {
  taskRunId: string;
  xPrefectApiVersion?: string;
}) => queryClient.prefetchQuery({ queryKey: Common.UseTaskRunStatesServiceGetTaskRunStatesKeyFn({ taskRunId, xPrefectApiVersion }), queryFn: () => TaskRunStatesService.getTaskRunStates({ taskRunId, xPrefectApiVersion }) });
export const prefetchUseFlowRunNotificationPoliciesServiceGetFlowRunNotificationPoliciesById = (queryClient: QueryClient, { id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}) => queryClient.prefetchQuery({ queryKey: Common.UseFlowRunNotificationPoliciesServiceGetFlowRunNotificationPoliciesByIdKeyFn({ id, xPrefectApiVersion }), queryFn: () => FlowRunNotificationPoliciesService.getFlowRunNotificationPoliciesById({ id, xPrefectApiVersion }) });
export const prefetchUseDeploymentsServiceGetDeploymentsById = (queryClient: QueryClient, { id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}) => queryClient.prefetchQuery({ queryKey: Common.UseDeploymentsServiceGetDeploymentsByIdKeyFn({ id, xPrefectApiVersion }), queryFn: () => DeploymentsService.getDeploymentsById({ id, xPrefectApiVersion }) });
export const prefetchUseDeploymentsServiceGetDeploymentsNameByFlowNameByDeploymentName = (queryClient: QueryClient, { deploymentName, flowName, xPrefectApiVersion }: {
  deploymentName: string;
  flowName: string;
  xPrefectApiVersion?: string;
}) => queryClient.prefetchQuery({ queryKey: Common.UseDeploymentsServiceGetDeploymentsNameByFlowNameByDeploymentNameKeyFn({ deploymentName, flowName, xPrefectApiVersion }), queryFn: () => DeploymentsService.getDeploymentsNameByFlowNameByDeploymentName({ deploymentName, flowName, xPrefectApiVersion }) });
export const prefetchUseDeploymentsServiceGetDeploymentsByIdWorkQueueCheck = (queryClient: QueryClient, { id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}) => queryClient.prefetchQuery({ queryKey: Common.UseDeploymentsServiceGetDeploymentsByIdWorkQueueCheckKeyFn({ id, xPrefectApiVersion }), queryFn: () => DeploymentsService.getDeploymentsByIdWorkQueueCheck({ id, xPrefectApiVersion }) });
export const prefetchUseDeploymentsServiceGetDeploymentsByIdSchedules = (queryClient: QueryClient, { id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}) => queryClient.prefetchQuery({ queryKey: Common.UseDeploymentsServiceGetDeploymentsByIdSchedulesKeyFn({ id, xPrefectApiVersion }), queryFn: () => DeploymentsService.getDeploymentsByIdSchedules({ id, xPrefectApiVersion }) });
export const prefetchUseSavedSearchesServiceGetSavedSearchesById = (queryClient: QueryClient, { id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}) => queryClient.prefetchQuery({ queryKey: Common.UseSavedSearchesServiceGetSavedSearchesByIdKeyFn({ id, xPrefectApiVersion }), queryFn: () => SavedSearchesService.getSavedSearchesById({ id, xPrefectApiVersion }) });
export const prefetchUseConcurrencyLimitsServiceGetConcurrencyLimitsById = (queryClient: QueryClient, { id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}) => queryClient.prefetchQuery({ queryKey: Common.UseConcurrencyLimitsServiceGetConcurrencyLimitsByIdKeyFn({ id, xPrefectApiVersion }), queryFn: () => ConcurrencyLimitsService.getConcurrencyLimitsById({ id, xPrefectApiVersion }) });
export const prefetchUseConcurrencyLimitsServiceGetConcurrencyLimitsTagByTag = (queryClient: QueryClient, { tag, xPrefectApiVersion }: {
  tag: string;
  xPrefectApiVersion?: string;
}) => queryClient.prefetchQuery({ queryKey: Common.UseConcurrencyLimitsServiceGetConcurrencyLimitsTagByTagKeyFn({ tag, xPrefectApiVersion }), queryFn: () => ConcurrencyLimitsService.getConcurrencyLimitsTagByTag({ tag, xPrefectApiVersion }) });
export const prefetchUseConcurrencyLimitsV2ServiceGetV2ConcurrencyLimitsByIdOrName = (queryClient: QueryClient, { idOrName, xPrefectApiVersion }: {
  idOrName: string;
  xPrefectApiVersion?: string;
}) => queryClient.prefetchQuery({ queryKey: Common.UseConcurrencyLimitsV2ServiceGetV2ConcurrencyLimitsByIdOrNameKeyFn({ idOrName, xPrefectApiVersion }), queryFn: () => ConcurrencyLimitsV2Service.getV2ConcurrencyLimitsByIdOrName({ idOrName, xPrefectApiVersion }) });
export const prefetchUseBlockTypesServiceGetBlockTypesById = (queryClient: QueryClient, { id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}) => queryClient.prefetchQuery({ queryKey: Common.UseBlockTypesServiceGetBlockTypesByIdKeyFn({ id, xPrefectApiVersion }), queryFn: () => BlockTypesService.getBlockTypesById({ id, xPrefectApiVersion }) });
export const prefetchUseBlockTypesServiceGetBlockTypesSlugBySlug = (queryClient: QueryClient, { slug, xPrefectApiVersion }: {
  slug: string;
  xPrefectApiVersion?: string;
}) => queryClient.prefetchQuery({ queryKey: Common.UseBlockTypesServiceGetBlockTypesSlugBySlugKeyFn({ slug, xPrefectApiVersion }), queryFn: () => BlockTypesService.getBlockTypesSlugBySlug({ slug, xPrefectApiVersion }) });
export const prefetchUseBlockTypesServiceGetBlockTypesSlugBySlugBlockDocuments = (queryClient: QueryClient, { includeSecrets, slug, xPrefectApiVersion }: {
  includeSecrets?: boolean;
  slug: string;
  xPrefectApiVersion?: string;
}) => queryClient.prefetchQuery({ queryKey: Common.UseBlockTypesServiceGetBlockTypesSlugBySlugBlockDocumentsKeyFn({ includeSecrets, slug, xPrefectApiVersion }), queryFn: () => BlockTypesService.getBlockTypesSlugBySlugBlockDocuments({ includeSecrets, slug, xPrefectApiVersion }) });
export const prefetchUseBlockTypesServiceGetBlockTypesSlugBySlugBlockDocumentsNameByBlockDocumentName = (queryClient: QueryClient, { blockDocumentName, includeSecrets, slug, xPrefectApiVersion }: {
  blockDocumentName: string;
  includeSecrets?: boolean;
  slug: string;
  xPrefectApiVersion?: string;
}) => queryClient.prefetchQuery({ queryKey: Common.UseBlockTypesServiceGetBlockTypesSlugBySlugBlockDocumentsNameByBlockDocumentNameKeyFn({ blockDocumentName, includeSecrets, slug, xPrefectApiVersion }), queryFn: () => BlockTypesService.getBlockTypesSlugBySlugBlockDocumentsNameByBlockDocumentName({ blockDocumentName, includeSecrets, slug, xPrefectApiVersion }) });
export const prefetchUseBlockDocumentsServiceGetBlockTypesSlugBySlugBlockDocuments = (queryClient: QueryClient, { includeSecrets, slug, xPrefectApiVersion }: {
  includeSecrets?: boolean;
  slug: string;
  xPrefectApiVersion?: string;
}) => queryClient.prefetchQuery({ queryKey: Common.UseBlockDocumentsServiceGetBlockTypesSlugBySlugBlockDocumentsKeyFn({ includeSecrets, slug, xPrefectApiVersion }), queryFn: () => BlockDocumentsService.getBlockTypesSlugBySlugBlockDocuments({ includeSecrets, slug, xPrefectApiVersion }) });
export const prefetchUseBlockDocumentsServiceGetBlockTypesSlugBySlugBlockDocumentsNameByBlockDocumentName = (queryClient: QueryClient, { blockDocumentName, includeSecrets, slug, xPrefectApiVersion }: {
  blockDocumentName: string;
  includeSecrets?: boolean;
  slug: string;
  xPrefectApiVersion?: string;
}) => queryClient.prefetchQuery({ queryKey: Common.UseBlockDocumentsServiceGetBlockTypesSlugBySlugBlockDocumentsNameByBlockDocumentNameKeyFn({ blockDocumentName, includeSecrets, slug, xPrefectApiVersion }), queryFn: () => BlockDocumentsService.getBlockTypesSlugBySlugBlockDocumentsNameByBlockDocumentName({ blockDocumentName, includeSecrets, slug, xPrefectApiVersion }) });
export const prefetchUseBlockDocumentsServiceGetBlockDocumentsById = (queryClient: QueryClient, { id, includeSecrets, xPrefectApiVersion }: {
  id: string;
  includeSecrets?: boolean;
  xPrefectApiVersion?: string;
}) => queryClient.prefetchQuery({ queryKey: Common.UseBlockDocumentsServiceGetBlockDocumentsByIdKeyFn({ id, includeSecrets, xPrefectApiVersion }), queryFn: () => BlockDocumentsService.getBlockDocumentsById({ id, includeSecrets, xPrefectApiVersion }) });
export const prefetchUseWorkPoolsServiceGetWorkPoolsByName = (queryClient: QueryClient, { name, xPrefectApiVersion }: {
  name: string;
  xPrefectApiVersion?: string;
}) => queryClient.prefetchQuery({ queryKey: Common.UseWorkPoolsServiceGetWorkPoolsByNameKeyFn({ name, xPrefectApiVersion }), queryFn: () => WorkPoolsService.getWorkPoolsByName({ name, xPrefectApiVersion }) });
export const prefetchUseWorkPoolsServiceGetWorkPoolsByWorkPoolNameQueuesByName = (queryClient: QueryClient, { name, workPoolName, xPrefectApiVersion }: {
  name: string;
  workPoolName: string;
  xPrefectApiVersion?: string;
}) => queryClient.prefetchQuery({ queryKey: Common.UseWorkPoolsServiceGetWorkPoolsByWorkPoolNameQueuesByNameKeyFn({ name, workPoolName, xPrefectApiVersion }), queryFn: () => WorkPoolsService.getWorkPoolsByWorkPoolNameQueuesByName({ name, workPoolName, xPrefectApiVersion }) });
export const prefetchUseWorkQueuesServiceGetWorkQueuesById = (queryClient: QueryClient, { id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}) => queryClient.prefetchQuery({ queryKey: Common.UseWorkQueuesServiceGetWorkQueuesByIdKeyFn({ id, xPrefectApiVersion }), queryFn: () => WorkQueuesService.getWorkQueuesById({ id, xPrefectApiVersion }) });
export const prefetchUseWorkQueuesServiceGetWorkQueuesNameByName = (queryClient: QueryClient, { name, xPrefectApiVersion }: {
  name: string;
  xPrefectApiVersion?: string;
}) => queryClient.prefetchQuery({ queryKey: Common.UseWorkQueuesServiceGetWorkQueuesNameByNameKeyFn({ name, xPrefectApiVersion }), queryFn: () => WorkQueuesService.getWorkQueuesNameByName({ name, xPrefectApiVersion }) });
export const prefetchUseWorkQueuesServiceGetWorkQueuesByIdStatus = (queryClient: QueryClient, { id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}) => queryClient.prefetchQuery({ queryKey: Common.UseWorkQueuesServiceGetWorkQueuesByIdStatusKeyFn({ id, xPrefectApiVersion }), queryFn: () => WorkQueuesService.getWorkQueuesByIdStatus({ id, xPrefectApiVersion }) });
export const prefetchUseArtifactsServiceGetArtifactsById = (queryClient: QueryClient, { id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}) => queryClient.prefetchQuery({ queryKey: Common.UseArtifactsServiceGetArtifactsByIdKeyFn({ id, xPrefectApiVersion }), queryFn: () => ArtifactsService.getArtifactsById({ id, xPrefectApiVersion }) });
export const prefetchUseArtifactsServiceGetArtifactsByKeyLatest = (queryClient: QueryClient, { key, xPrefectApiVersion }: {
  key: string;
  xPrefectApiVersion?: string;
}) => queryClient.prefetchQuery({ queryKey: Common.UseArtifactsServiceGetArtifactsByKeyLatestKeyFn({ key, xPrefectApiVersion }), queryFn: () => ArtifactsService.getArtifactsByKeyLatest({ key, xPrefectApiVersion }) });
export const prefetchUseBlockSchemasServiceGetBlockSchemasById = (queryClient: QueryClient, { id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}) => queryClient.prefetchQuery({ queryKey: Common.UseBlockSchemasServiceGetBlockSchemasByIdKeyFn({ id, xPrefectApiVersion }), queryFn: () => BlockSchemasService.getBlockSchemasById({ id, xPrefectApiVersion }) });
export const prefetchUseBlockSchemasServiceGetBlockSchemasChecksumByChecksum = (queryClient: QueryClient, { checksum, version, xPrefectApiVersion }: {
  checksum: string;
  version?: string;
  xPrefectApiVersion?: string;
}) => queryClient.prefetchQuery({ queryKey: Common.UseBlockSchemasServiceGetBlockSchemasChecksumByChecksumKeyFn({ checksum, version, xPrefectApiVersion }), queryFn: () => BlockSchemasService.getBlockSchemasChecksumByChecksum({ checksum, version, xPrefectApiVersion }) });
export const prefetchUseBlockCapabilitiesServiceGetBlockCapabilities = (queryClient: QueryClient, { xPrefectApiVersion }: {
  xPrefectApiVersion?: string;
} = {}) => queryClient.prefetchQuery({ queryKey: Common.UseBlockCapabilitiesServiceGetBlockCapabilitiesKeyFn({ xPrefectApiVersion }), queryFn: () => BlockCapabilitiesService.getBlockCapabilities({ xPrefectApiVersion }) });
export const prefetchUseCollectionsServiceGetCollectionsViewsByView = (queryClient: QueryClient, { view, xPrefectApiVersion }: {
  view: string;
  xPrefectApiVersion?: string;
}) => queryClient.prefetchQuery({ queryKey: Common.UseCollectionsServiceGetCollectionsViewsByViewKeyFn({ view, xPrefectApiVersion }), queryFn: () => CollectionsService.getCollectionsViewsByView({ view, xPrefectApiVersion }) });
export const prefetchUseVariablesServiceGetVariablesById = (queryClient: QueryClient, { id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}) => queryClient.prefetchQuery({ queryKey: Common.UseVariablesServiceGetVariablesByIdKeyFn({ id, xPrefectApiVersion }), queryFn: () => VariablesService.getVariablesById({ id, xPrefectApiVersion }) });
export const prefetchUseVariablesServiceGetVariablesNameByName = (queryClient: QueryClient, { name, xPrefectApiVersion }: {
  name: string;
  xPrefectApiVersion?: string;
}) => queryClient.prefetchQuery({ queryKey: Common.UseVariablesServiceGetVariablesNameByNameKeyFn({ name, xPrefectApiVersion }), queryFn: () => VariablesService.getVariablesNameByName({ name, xPrefectApiVersion }) });
export const prefetchUseDefaultServiceGetCsrfToken = (queryClient: QueryClient, { client, xPrefectApiVersion }: {
  client: string;
  xPrefectApiVersion?: string;
}) => queryClient.prefetchQuery({ queryKey: Common.UseDefaultServiceGetCsrfTokenKeyFn({ client, xPrefectApiVersion }), queryFn: () => DefaultService.getCsrfToken({ client, xPrefectApiVersion }) });
export const prefetchUseEventsServiceGetEventsFilterNext = (queryClient: QueryClient, { pageToken, xPrefectApiVersion }: {
  pageToken: string;
  xPrefectApiVersion?: string;
}) => queryClient.prefetchQuery({ queryKey: Common.UseEventsServiceGetEventsFilterNextKeyFn({ pageToken, xPrefectApiVersion }), queryFn: () => EventsService.getEventsFilterNext({ pageToken, xPrefectApiVersion }) });
export const prefetchUseAutomationsServiceGetAutomationsById = (queryClient: QueryClient, { id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}) => queryClient.prefetchQuery({ queryKey: Common.UseAutomationsServiceGetAutomationsByIdKeyFn({ id, xPrefectApiVersion }), queryFn: () => AutomationsService.getAutomationsById({ id, xPrefectApiVersion }) });
export const prefetchUseAutomationsServiceGetAutomationsRelatedToByResourceId = (queryClient: QueryClient, { resourceId, xPrefectApiVersion }: {
  resourceId: string;
  xPrefectApiVersion?: string;
}) => queryClient.prefetchQuery({ queryKey: Common.UseAutomationsServiceGetAutomationsRelatedToByResourceIdKeyFn({ resourceId, xPrefectApiVersion }), queryFn: () => AutomationsService.getAutomationsRelatedToByResourceId({ resourceId, xPrefectApiVersion }) });
export const prefetchUseAdminServiceGetAdminSettings = (queryClient: QueryClient, { xPrefectApiVersion }: {
  xPrefectApiVersion?: string;
} = {}) => queryClient.prefetchQuery({ queryKey: Common.UseAdminServiceGetAdminSettingsKeyFn({ xPrefectApiVersion }), queryFn: () => AdminService.getAdminSettings({ xPrefectApiVersion }) });
export const prefetchUseAdminServiceGetAdminVersion = (queryClient: QueryClient, { xPrefectApiVersion }: {
  xPrefectApiVersion?: string;
} = {}) => queryClient.prefetchQuery({ queryKey: Common.UseAdminServiceGetAdminVersionKeyFn({ xPrefectApiVersion }), queryFn: () => AdminService.getAdminVersion({ xPrefectApiVersion }) });
