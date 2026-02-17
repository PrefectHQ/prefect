import { test as base, expect } from "@playwright/test";
import { createPrefectApiClient, type PrefectApiClient } from "./api-client";

type Fixtures = {
	apiClient: PrefectApiClient;
};

export const test = base.extend<Fixtures>({
	// biome-ignore lint/correctness/noEmptyPattern: Playwright fixtures require object destructuring syntax
	apiClient: async ({}, use) => {
		const client = createPrefectApiClient();
		await use(client);
	},
});

export { expect };
export type { PrefectApiClient } from "./api-client";
export {
	type Artifact,
	type Automation,
	type BlockDocument,
	type BlockSchema,
	type BlockType,
	cleanupArtifacts,
	cleanupAutomations,
	cleanupBlockDocuments,
	cleanupDeployments,
	cleanupFlowRuns,
	cleanupFlows,
	cleanupGlobalConcurrencyLimits,
	cleanupTaskRunConcurrencyLimits,
	cleanupVariables,
	cleanupWorkPools,
	createArtifact,
	createBlockDocument,
	createDeployment,
	createFlow,
	createFlowRun,
	createGlobalConcurrencyLimit,
	createLinkArtifact,
	createLogs,
	createMarkdownArtifact,
	createTableArtifact,
	createTaskRunConcurrencyLimit,
	createVariable,
	createWorkPool,
	type Deployment,
	deleteArtifact,
	deleteAutomation,
	deleteBlockDocument,
	deleteDeployment,
	deleteFlow,
	deleteFlowRun,
	deleteGlobalConcurrencyLimit,
	deleteTaskRunConcurrencyLimit,
	deleteVariable,
	deleteWorkPool,
	type Flow,
	type FlowRun,
	type GlobalConcurrencyLimit,
	getBlockTypeBySlug,
	getWorkPool,
	listArtifacts,
	listAutomations,
	listBlockDocuments,
	listBlockSchemas,
	listBlockTypes,
	listDeployments,
	listFlowRuns,
	listFlows,
	listGlobalConcurrencyLimits,
	listTaskRunConcurrencyLimits,
	listVariables,
	listWorkPoolQueues,
	listWorkPools,
	type TaskRunConcurrencyLimit,
	type Variable,
	type WorkPool,
	type WorkPoolQueue,
	waitForServerHealth,
} from "./api-helpers/index";
export {
	clearAuthCredentials,
	getAuthCredentials,
	isAuthRequired,
	setAuthCredentials,
} from "./auth-helpers";
export {
	type FlowWithTasksResult,
	type ParentChildResult,
	runFlowWithTasks,
	runParentChild,
	runSimpleTask,
	type SimpleTaskResult,
} from "./run-python-flow";
