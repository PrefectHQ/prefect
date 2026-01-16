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
	cleanupGlobalConcurrencyLimits,
	cleanupTaskRunConcurrencyLimits,
	cleanupVariables,
	createBlockDocument,
	createDeployment,
	createFlow,
	createGlobalConcurrencyLimit,
	createTaskRunConcurrencyLimit,
	createVariable,
	type Deployment,
	deleteAutomation,
	deleteBlockDocument,
	deleteGlobalConcurrencyLimit,
	deleteTaskRunConcurrencyLimit,
	deleteVariable,
	type Flow,
	type GlobalConcurrencyLimit,
	getBlockTypeBySlug,
	listAutomations,
	listBlockDocuments,
	listBlockSchemas,
	listBlockTypes,
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
