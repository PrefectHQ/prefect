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
	cleanupAutomations,
	createDeployment,
	createFlow,
	type Deployment,
	deleteAutomation,
	type Flow,
	listAutomations,
	waitForServerHealth,
} from "./api-helpers";
