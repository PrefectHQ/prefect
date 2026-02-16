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
	type Automation,
	type BlockDocument,
	type BlockSchema,
	type BlockType,
	cleanupAutomations,
	cleanupBlockDocuments,
	cleanupDeployments,
	cleanupFlowRuns,
	cleanupFlows,
	cleanupGlobalConcurrencyLimits,
	cleanupTaskRunConcurrencyLimits,
	cleanupVariables,
	createBlockDocument,
	createDeployment,
	createFlow,
	createFlowRun,
	createGlobalConcurrencyLimit,
	createLogs,
	createTaskRunConcurrencyLimit,
	createVariable,
	type Deployment,
	deleteAutomation,
	deleteBlockDocument,
	deleteDeployment,
	deleteFlow,
	deleteFlowRun,
	deleteGlobalConcurrencyLimit,
	deleteTaskRunConcurrencyLimit,
	deleteVariable,
	type Flow,
	type FlowRun,
	type GlobalConcurrencyLimit,
	getBlockTypeBySlug,
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
	type TaskRunConcurrencyLimit,
	type Variable,
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
