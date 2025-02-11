// generated with @7nohe/openapi-react-query-codegen@1.6.2 

import { type QueryClient } from "@tanstack/react-query";
import { AdminService, ArtifactsService, AutomationsService, BlockCapabilitiesService, BlockDocumentsService, BlockSchemasService, BlockTypesService, CollectionsService, ConcurrencyLimitsService, ConcurrencyLimitsV2Service, DefaultService, DeploymentsService, EventsService, FlowRunNotificationPoliciesService, FlowRunStatesService, FlowRunsService, FlowsService, RootService, SavedSearchesService, TaskRunStatesService, TaskRunsService, VariablesService, WorkPoolsService, WorkQueuesService } from "../requests/services.gen";
import * as Common from "./common";
export const ensureUseRootServiceGetHealthData = (queryClient: QueryClient) => queryClient.ensureQueryData({ queryKey: Common.UseRootServiceGetHealthKeyFn(), queryFn: () => RootService.getHealth() });
export const ensureUseRootServiceGetVersionData = (queryClient: QueryClient) => queryClient.ensureQueryData({ queryKey: Common.UseRootServiceGetVersionKeyFn(), queryFn: () => RootService.getVersion() });
export const ensureUseRootServiceGetHelloData = (queryClient: QueryClient, { xPrefectApiVersion }: {
  xPrefectApiVersion?: string;
} = {}) => queryClient.ensureQueryData({ queryKey: Common.UseRootServiceGetHelloKeyFn({ xPrefectApiVersion }), queryFn: () => RootService.getHello({ xPrefectApiVersion }) });
export const ensureUseRootServiceGetReadyData = (queryClient: QueryClient, { xPrefectApiVersion }: {
  xPrefectApiVersion?: string;
} = {}) => queryClient.ensureQueryData({ queryKey: Common.UseRootServiceGetReadyKeyFn({ xPrefectApiVersion }), queryFn: () => RootService.getReady({ xPrefectApiVersion }) });
export const ensureUseFlowsServiceGetFlowsByIdData = (queryClient: QueryClient, { id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}) => queryClient.ensureQueryData({ queryKey: Common.UseFlowsServiceGetFlowsByIdKeyFn({ id, xPrefectApiVersion }), queryFn: () => FlowsService.getFlowsById({ id, xPrefectApiVersion }) });
export const ensureUseFlowsServiceGetFlowsNameByNameData = (queryClient: QueryClient, { name, xPrefectApiVersion }: {
  name: string;
  xPrefectApiVersion?: string;
}) => queryClient.ensureQueryData({ queryKey: Common.UseFlowsServiceGetFlowsNameByNameKeyFn({ name, xPrefectApiVersion }), queryFn: () => FlowsService.getFlowsNameByName({ name, xPrefectApiVersion }) });
export const ensureUseFlowRunsServiceGetFlowRunsByIdData = (queryClient: QueryClient, { id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}) => queryClient.ensureQueryData({ queryKey: Common.UseFlowRunsServiceGetFlowRunsByIdKeyFn({ id, xPrefectApiVersion }), queryFn: () => FlowRunsService.getFlowRunsById({ id, xPrefectApiVersion }) });
export const ensureUseFlowRunsServiceGetFlowRunsByIdGraphData = (queryClient: QueryClient, { id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}) => queryClient.ensureQueryData({ queryKey: Common.UseFlowRunsServiceGetFlowRunsByIdGraphKeyFn({ id, xPrefectApiVersion }), queryFn: () => FlowRunsService.getFlowRunsByIdGraph({ id, xPrefectApiVersion }) });
export const ensureUseFlowRunsServiceGetFlowRunsByIdGraphV2Data = (queryClient: QueryClient, { id, since, xPrefectApiVersion }: {
  id: string;
  since?: string;
  xPrefectApiVersion?: string;
}) => queryClient.ensureQueryData({ queryKey: Common.UseFlowRunsServiceGetFlowRunsByIdGraphV2KeyFn({ id, since, xPrefectApiVersion }), queryFn: () => FlowRunsService.getFlowRunsByIdGraphV2({ id, since, xPrefectApiVersion }) });
export const ensureUseFlowRunsServiceGetFlowRunsByIdInputByKeyData = (queryClient: QueryClient, { id, key, xPrefectApiVersion }: {
  id: string;
  key: string;
  xPrefectApiVersion?: string;
}) => queryClient.ensureQueryData({ queryKey: Common.UseFlowRunsServiceGetFlowRunsByIdInputByKeyKeyFn({ id, key, xPrefectApiVersion }), queryFn: () => FlowRunsService.getFlowRunsByIdInputByKey({ id, key, xPrefectApiVersion }) });
export const ensureUseFlowRunsServiceGetFlowRunsByIdLogsDownloadData = (queryClient: QueryClient, { id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}) => queryClient.ensureQueryData({ queryKey: Common.UseFlowRunsServiceGetFlowRunsByIdLogsDownloadKeyFn({ id, xPrefectApiVersion }), queryFn: () => FlowRunsService.getFlowRunsByIdLogsDownload({ id, xPrefectApiVersion }) });
export const ensureUseTaskRunsServiceGetTaskRunsByIdData = (queryClient: QueryClient, { id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}) => queryClient.ensureQueryData({ queryKey: Common.UseTaskRunsServiceGetTaskRunsByIdKeyFn({ id, xPrefectApiVersion }), queryFn: () => TaskRunsService.getTaskRunsById({ id, xPrefectApiVersion }) });
export const ensureUseFlowRunStatesServiceGetFlowRunStatesByIdData = (queryClient: QueryClient, { id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}) => queryClient.ensureQueryData({ queryKey: Common.UseFlowRunStatesServiceGetFlowRunStatesByIdKeyFn({ id, xPrefectApiVersion }), queryFn: () => FlowRunStatesService.getFlowRunStatesById({ id, xPrefectApiVersion }) });
export const ensureUseFlowRunStatesServiceGetFlowRunStatesData = (queryClient: QueryClient, { flowRunId, xPrefectApiVersion }: {
  flowRunId: string;
  xPrefectApiVersion?: string;
}) => queryClient.ensureQueryData({ queryKey: Common.UseFlowRunStatesServiceGetFlowRunStatesKeyFn({ flowRunId, xPrefectApiVersion }), queryFn: () => FlowRunStatesService.getFlowRunStates({ flowRunId, xPrefectApiVersion }) });
export const ensureUseTaskRunStatesServiceGetTaskRunStatesByIdData = (queryClient: QueryClient, { id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}) => queryClient.ensureQueryData({ queryKey: Common.UseTaskRunStatesServiceGetTaskRunStatesByIdKeyFn({ id, xPrefectApiVersion }), queryFn: () => TaskRunStatesService.getTaskRunStatesById({ id, xPrefectApiVersion }) });
export const ensureUseTaskRunStatesServiceGetTaskRunStatesData = (queryClient: QueryClient, { taskRunId, xPrefectApiVersion }: {
  taskRunId: string;
  xPrefectApiVersion?: string;
}) => queryClient.ensureQueryData({ queryKey: Common.UseTaskRunStatesServiceGetTaskRunStatesKeyFn({ taskRunId, xPrefectApiVersion }), queryFn: () => TaskRunStatesService.getTaskRunStates({ taskRunId, xPrefectApiVersion }) });
export const ensureUseFlowRunNotificationPoliciesServiceGetFlowRunNotificationPoliciesByIdData = (queryClient: QueryClient, { id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}) => queryClient.ensureQueryData({ queryKey: Common.UseFlowRunNotificationPoliciesServiceGetFlowRunNotificationPoliciesByIdKeyFn({ id, xPrefectApiVersion }), queryFn: () => FlowRunNotificationPoliciesService.getFlowRunNotificationPoliciesById({ id, xPrefectApiVersion }) });
export const ensureUseDeploymentsServiceGetDeploymentsByIdData = (queryClient: QueryClient, { id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}) => queryClient.ensureQueryData({ queryKey: Common.UseDeploymentsServiceGetDeploymentsByIdKeyFn({ id, xPrefectApiVersion }), queryFn: () => DeploymentsService.getDeploymentsById({ id, xPrefectApiVersion }) });
export const ensureUseDeploymentsServiceGetDeploymentsNameByFlowNameByDeploymentNameData = (queryClient: QueryClient, { deploymentName, flowName, xPrefectApiVersion }: {
  deploymentName: string;
  flowName: string;
  xPrefectApiVersion?: string;
}) => queryClient.ensureQueryData({ queryKey: Common.UseDeploymentsServiceGetDeploymentsNameByFlowNameByDeploymentNameKeyFn({ deploymentName, flowName, xPrefectApiVersion }), queryFn: () => DeploymentsService.getDeploymentsNameByFlowNameByDeploymentName({ deploymentName, flowName, xPrefectApiVersion }) });
export const ensureUseDeploymentsServiceGetDeploymentsByIdWorkQueueCheckData = (queryClient: QueryClient, { id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}) => queryClient.ensureQueryData({ queryKey: Common.UseDeploymentsServiceGetDeploymentsByIdWorkQueueCheckKeyFn({ id, xPrefectApiVersion }), queryFn: () => DeploymentsService.getDeploymentsByIdWorkQueueCheck({ id, xPrefectApiVersion }) });
export const ensureUseDeploymentsServiceGetDeploymentsByIdSchedulesData = (queryClient: QueryClient, { id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}) => queryClient.ensureQueryData({ queryKey: Common.UseDeploymentsServiceGetDeploymentsByIdSchedulesKeyFn({ id, xPrefectApiVersion }), queryFn: () => DeploymentsService.getDeploymentsByIdSchedules({ id, xPrefectApiVersion }) });
export const ensureUseSavedSearchesServiceGetSavedSearchesByIdData = (queryClient: QueryClient, { id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}) => queryClient.ensureQueryData({ queryKey: Common.UseSavedSearchesServiceGetSavedSearchesByIdKeyFn({ id, xPrefectApiVersion }), queryFn: () => SavedSearchesService.getSavedSearchesById({ id, xPrefectApiVersion }) });
export const ensureUseConcurrencyLimitsServiceGetConcurrencyLimitsByIdData = (queryClient: QueryClient, { id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}) => queryClient.ensureQueryData({ queryKey: Common.UseConcurrencyLimitsServiceGetConcurrencyLimitsByIdKeyFn({ id, xPrefectApiVersion }), queryFn: () => ConcurrencyLimitsService.getConcurrencyLimitsById({ id, xPrefectApiVersion }) });
export const ensureUseConcurrencyLimitsServiceGetConcurrencyLimitsTagByTagData = (queryClient: QueryClient, { tag, xPrefectApiVersion }: {
  tag: string;
  xPrefectApiVersion?: string;
}) => queryClient.ensureQueryData({ queryKey: Common.UseConcurrencyLimitsServiceGetConcurrencyLimitsTagByTagKeyFn({ tag, xPrefectApiVersion }), queryFn: () => ConcurrencyLimitsService.getConcurrencyLimitsTagByTag({ tag, xPrefectApiVersion }) });
export const ensureUseConcurrencyLimitsV2ServiceGetV2ConcurrencyLimitsByIdOrNameData = (queryClient: QueryClient, { idOrName, xPrefectApiVersion }: {
  idOrName: string;
  xPrefectApiVersion?: string;
}) => queryClient.ensureQueryData({ queryKey: Common.UseConcurrencyLimitsV2ServiceGetV2ConcurrencyLimitsByIdOrNameKeyFn({ idOrName, xPrefectApiVersion }), queryFn: () => ConcurrencyLimitsV2Service.getV2ConcurrencyLimitsByIdOrName({ idOrName, xPrefectApiVersion }) });
export const ensureUseBlockTypesServiceGetBlockTypesByIdData = (queryClient: QueryClient, { id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}) => queryClient.ensureQueryData({ queryKey: Common.UseBlockTypesServiceGetBlockTypesByIdKeyFn({ id, xPrefectApiVersion }), queryFn: () => BlockTypesService.getBlockTypesById({ id, xPrefectApiVersion }) });
export const ensureUseBlockTypesServiceGetBlockTypesSlugBySlugData = (queryClient: QueryClient, { slug, xPrefectApiVersion }: {
  slug: string;
  xPrefectApiVersion?: string;
}) => queryClient.ensureQueryData({ queryKey: Common.UseBlockTypesServiceGetBlockTypesSlugBySlugKeyFn({ slug, xPrefectApiVersion }), queryFn: () => BlockTypesService.getBlockTypesSlugBySlug({ slug, xPrefectApiVersion }) });
export const ensureUseBlockTypesServiceGetBlockTypesSlugBySlugBlockDocumentsData = (queryClient: QueryClient, { includeSecrets, slug, xPrefectApiVersion }: {
  includeSecrets?: boolean;
  slug: string;
  xPrefectApiVersion?: string;
}) => queryClient.ensureQueryData({ queryKey: Common.UseBlockTypesServiceGetBlockTypesSlugBySlugBlockDocumentsKeyFn({ includeSecrets, slug, xPrefectApiVersion }), queryFn: () => BlockTypesService.getBlockTypesSlugBySlugBlockDocuments({ includeSecrets, slug, xPrefectApiVersion }) });
export const ensureUseBlockTypesServiceGetBlockTypesSlugBySlugBlockDocumentsNameByBlockDocumentNameData = (queryClient: QueryClient, { blockDocumentName, includeSecrets, slug, xPrefectApiVersion }: {
  blockDocumentName: string;
  includeSecrets?: boolean;
  slug: string;
  xPrefectApiVersion?: string;
}) => queryClient.ensureQueryData({ queryKey: Common.UseBlockTypesServiceGetBlockTypesSlugBySlugBlockDocumentsNameByBlockDocumentNameKeyFn({ blockDocumentName, includeSecrets, slug, xPrefectApiVersion }), queryFn: () => BlockTypesService.getBlockTypesSlugBySlugBlockDocumentsNameByBlockDocumentName({ blockDocumentName, includeSecrets, slug, xPrefectApiVersion }) });
export const ensureUseBlockDocumentsServiceGetBlockTypesSlugBySlugBlockDocumentsData = (queryClient: QueryClient, { includeSecrets, slug, xPrefectApiVersion }: {
  includeSecrets?: boolean;
  slug: string;
  xPrefectApiVersion?: string;
}) => queryClient.ensureQueryData({ queryKey: Common.UseBlockDocumentsServiceGetBlockTypesSlugBySlugBlockDocumentsKeyFn({ includeSecrets, slug, xPrefectApiVersion }), queryFn: () => BlockDocumentsService.getBlockTypesSlugBySlugBlockDocuments({ includeSecrets, slug, xPrefectApiVersion }) });
export const ensureUseBlockDocumentsServiceGetBlockTypesSlugBySlugBlockDocumentsNameByBlockDocumentNameData = (queryClient: QueryClient, { blockDocumentName, includeSecrets, slug, xPrefectApiVersion }: {
  blockDocumentName: string;
  includeSecrets?: boolean;
  slug: string;
  xPrefectApiVersion?: string;
}) => queryClient.ensureQueryData({ queryKey: Common.UseBlockDocumentsServiceGetBlockTypesSlugBySlugBlockDocumentsNameByBlockDocumentNameKeyFn({ blockDocumentName, includeSecrets, slug, xPrefectApiVersion }), queryFn: () => BlockDocumentsService.getBlockTypesSlugBySlugBlockDocumentsNameByBlockDocumentName({ blockDocumentName, includeSecrets, slug, xPrefectApiVersion }) });
export const ensureUseBlockDocumentsServiceGetBlockDocumentsByIdData = (queryClient: QueryClient, { id, includeSecrets, xPrefectApiVersion }: {
  id: string;
  includeSecrets?: boolean;
  xPrefectApiVersion?: string;
}) => queryClient.ensureQueryData({ queryKey: Common.UseBlockDocumentsServiceGetBlockDocumentsByIdKeyFn({ id, includeSecrets, xPrefectApiVersion }), queryFn: () => BlockDocumentsService.getBlockDocumentsById({ id, includeSecrets, xPrefectApiVersion }) });
export const ensureUseWorkPoolsServiceGetWorkPoolsByNameData = (queryClient: QueryClient, { name, xPrefectApiVersion }: {
  name: string;
  xPrefectApiVersion?: string;
}) => queryClient.ensureQueryData({ queryKey: Common.UseWorkPoolsServiceGetWorkPoolsByNameKeyFn({ name, xPrefectApiVersion }), queryFn: () => WorkPoolsService.getWorkPoolsByName({ name, xPrefectApiVersion }) });
export const ensureUseWorkPoolsServiceGetWorkPoolsByWorkPoolNameQueuesByNameData = (queryClient: QueryClient, { name, workPoolName, xPrefectApiVersion }: {
  name: string;
  workPoolName: string;
  xPrefectApiVersion?: string;
}) => queryClient.ensureQueryData({ queryKey: Common.UseWorkPoolsServiceGetWorkPoolsByWorkPoolNameQueuesByNameKeyFn({ name, workPoolName, xPrefectApiVersion }), queryFn: () => WorkPoolsService.getWorkPoolsByWorkPoolNameQueuesByName({ name, workPoolName, xPrefectApiVersion }) });
export const ensureUseWorkQueuesServiceGetWorkQueuesByIdData = (queryClient: QueryClient, { id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}) => queryClient.ensureQueryData({ queryKey: Common.UseWorkQueuesServiceGetWorkQueuesByIdKeyFn({ id, xPrefectApiVersion }), queryFn: () => WorkQueuesService.getWorkQueuesById({ id, xPrefectApiVersion }) });
export const ensureUseWorkQueuesServiceGetWorkQueuesNameByNameData = (queryClient: QueryClient, { name, xPrefectApiVersion }: {
  name: string;
  xPrefectApiVersion?: string;
}) => queryClient.ensureQueryData({ queryKey: Common.UseWorkQueuesServiceGetWorkQueuesNameByNameKeyFn({ name, xPrefectApiVersion }), queryFn: () => WorkQueuesService.getWorkQueuesNameByName({ name, xPrefectApiVersion }) });
export const ensureUseWorkQueuesServiceGetWorkQueuesByIdStatusData = (queryClient: QueryClient, { id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}) => queryClient.ensureQueryData({ queryKey: Common.UseWorkQueuesServiceGetWorkQueuesByIdStatusKeyFn({ id, xPrefectApiVersion }), queryFn: () => WorkQueuesService.getWorkQueuesByIdStatus({ id, xPrefectApiVersion }) });
export const ensureUseArtifactsServiceGetArtifactsByIdData = (queryClient: QueryClient, { id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}) => queryClient.ensureQueryData({ queryKey: Common.UseArtifactsServiceGetArtifactsByIdKeyFn({ id, xPrefectApiVersion }), queryFn: () => ArtifactsService.getArtifactsById({ id, xPrefectApiVersion }) });
export const ensureUseArtifactsServiceGetArtifactsByKeyLatestData = (queryClient: QueryClient, { key, xPrefectApiVersion }: {
  key: string;
  xPrefectApiVersion?: string;
}) => queryClient.ensureQueryData({ queryKey: Common.UseArtifactsServiceGetArtifactsByKeyLatestKeyFn({ key, xPrefectApiVersion }), queryFn: () => ArtifactsService.getArtifactsByKeyLatest({ key, xPrefectApiVersion }) });
export const ensureUseBlockSchemasServiceGetBlockSchemasByIdData = (queryClient: QueryClient, { id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}) => queryClient.ensureQueryData({ queryKey: Common.UseBlockSchemasServiceGetBlockSchemasByIdKeyFn({ id, xPrefectApiVersion }), queryFn: () => BlockSchemasService.getBlockSchemasById({ id, xPrefectApiVersion }) });
export const ensureUseBlockSchemasServiceGetBlockSchemasChecksumByChecksumData = (queryClient: QueryClient, { checksum, version, xPrefectApiVersion }: {
  checksum: string;
  version?: string;
  xPrefectApiVersion?: string;
}) => queryClient.ensureQueryData({ queryKey: Common.UseBlockSchemasServiceGetBlockSchemasChecksumByChecksumKeyFn({ checksum, version, xPrefectApiVersion }), queryFn: () => BlockSchemasService.getBlockSchemasChecksumByChecksum({ checksum, version, xPrefectApiVersion }) });
export const ensureUseBlockCapabilitiesServiceGetBlockCapabilitiesData = (queryClient: QueryClient, { xPrefectApiVersion }: {
  xPrefectApiVersion?: string;
} = {}) => queryClient.ensureQueryData({ queryKey: Common.UseBlockCapabilitiesServiceGetBlockCapabilitiesKeyFn({ xPrefectApiVersion }), queryFn: () => BlockCapabilitiesService.getBlockCapabilities({ xPrefectApiVersion }) });
export const ensureUseCollectionsServiceGetCollectionsViewsByViewData = (queryClient: QueryClient, { view, xPrefectApiVersion }: {
  view: string;
  xPrefectApiVersion?: string;
}) => queryClient.ensureQueryData({ queryKey: Common.UseCollectionsServiceGetCollectionsViewsByViewKeyFn({ view, xPrefectApiVersion }), queryFn: () => CollectionsService.getCollectionsViewsByView({ view, xPrefectApiVersion }) });
export const ensureUseVariablesServiceGetVariablesByIdData = (queryClient: QueryClient, { id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}) => queryClient.ensureQueryData({ queryKey: Common.UseVariablesServiceGetVariablesByIdKeyFn({ id, xPrefectApiVersion }), queryFn: () => VariablesService.getVariablesById({ id, xPrefectApiVersion }) });
export const ensureUseVariablesServiceGetVariablesNameByNameData = (queryClient: QueryClient, { name, xPrefectApiVersion }: {
  name: string;
  xPrefectApiVersion?: string;
}) => queryClient.ensureQueryData({ queryKey: Common.UseVariablesServiceGetVariablesNameByNameKeyFn({ name, xPrefectApiVersion }), queryFn: () => VariablesService.getVariablesNameByName({ name, xPrefectApiVersion }) });
export const ensureUseDefaultServiceGetCsrfTokenData = (queryClient: QueryClient, { client, xPrefectApiVersion }: {
  client: string;
  xPrefectApiVersion?: string;
}) => queryClient.ensureQueryData({ queryKey: Common.UseDefaultServiceGetCsrfTokenKeyFn({ client, xPrefectApiVersion }), queryFn: () => DefaultService.getCsrfToken({ client, xPrefectApiVersion }) });
export const ensureUseEventsServiceGetEventsFilterNextData = (queryClient: QueryClient, { pageToken, xPrefectApiVersion }: {
  pageToken: string;
  xPrefectApiVersion?: string;
}) => queryClient.ensureQueryData({ queryKey: Common.UseEventsServiceGetEventsFilterNextKeyFn({ pageToken, xPrefectApiVersion }), queryFn: () => EventsService.getEventsFilterNext({ pageToken, xPrefectApiVersion }) });
export const ensureUseAutomationsServiceGetAutomationsByIdData = (queryClient: QueryClient, { id, xPrefectApiVersion }: {
  id: string;
  xPrefectApiVersion?: string;
}) => queryClient.ensureQueryData({ queryKey: Common.UseAutomationsServiceGetAutomationsByIdKeyFn({ id, xPrefectApiVersion }), queryFn: () => AutomationsService.getAutomationsById({ id, xPrefectApiVersion }) });
export const ensureUseAutomationsServiceGetAutomationsRelatedToByResourceIdData = (queryClient: QueryClient, { resourceId, xPrefectApiVersion }: {
  resourceId: string;
  xPrefectApiVersion?: string;
}) => queryClient.ensureQueryData({ queryKey: Common.UseAutomationsServiceGetAutomationsRelatedToByResourceIdKeyFn({ resourceId, xPrefectApiVersion }), queryFn: () => AutomationsService.getAutomationsRelatedToByResourceId({ resourceId, xPrefectApiVersion }) });
export const ensureUseAdminServiceGetAdminSettingsData = (queryClient: QueryClient, { xPrefectApiVersion }: {
  xPrefectApiVersion?: string;
} = {}) => queryClient.ensureQueryData({ queryKey: Common.UseAdminServiceGetAdminSettingsKeyFn({ xPrefectApiVersion }), queryFn: () => AdminService.getAdminSettings({ xPrefectApiVersion }) });
export const ensureUseAdminServiceGetAdminVersionData = (queryClient: QueryClient, { xPrefectApiVersion }: {
  xPrefectApiVersion?: string;
} = {}) => queryClient.ensureQueryData({ queryKey: Common.UseAdminServiceGetAdminVersionKeyFn({ xPrefectApiVersion }), queryFn: () => AdminService.getAdminVersion({ xPrefectApiVersion }) });
