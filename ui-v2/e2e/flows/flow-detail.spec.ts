import {
	cleanupFlowRuns,
	cleanupFlows,
	createDeployment,
	createFlow,
	createFlowRun,
	expect,
	test,
	waitForServerHealth,
} from "../fixtures";

const TEST_PREFIX = "e2e-flow-detail-";

test.describe("Flow Detail Page", () => {
	test.describe.configure({ mode: "serial" });

	test.beforeAll(async ({ apiClient }) => {
		await waitForServerHealth(apiClient);
	});

	test.beforeEach(async ({ apiClient }) => {
		try {
			await cleanupFlows(apiClient, TEST_PREFIX);
			await cleanupFlowRuns(apiClient, TEST_PREFIX);
		} catch {
			// Ignore cleanup errors
		}
	});

	test.afterEach(async ({ apiClient }) => {
		try {
			await cleanupFlows(apiClient, TEST_PREFIX);
			await cleanupFlowRuns(apiClient, TEST_PREFIX);
		} catch {
			// Ignore cleanup errors
		}
	});

	test("Navigation to detail and breadcrumb", async ({ page, apiClient }) => {
		const flowName = `${TEST_PREFIX}nav-${Date.now()}`;
		const flow = await createFlow(apiClient, flowName);

		await page.goto(`/flows/flow/${flow.id}`);

		await expect(page.getByText(flowName)).toBeVisible({ timeout: 10000 });
		await expect(page).toHaveURL(new RegExp(`/flows/flow/${flow.id}`));
		await expect(page.getByRole("tab", { name: "Runs" })).toBeVisible();
		await expect(page.getByRole("tab", { name: "Deployments" })).toBeVisible();
		await expect(page.getByRole("tab", { name: "Details" })).toBeVisible();
	});

	test("Flow metadata on Details tab", async ({ page, apiClient }) => {
		const flowName = `${TEST_PREFIX}meta-${Date.now()}`;
		const flow = await createFlow(apiClient, flowName);

		await page.goto(`/flows/flow/${flow.id}?tab=details`);

		await expect(page.getByText("Flow ID")).toBeVisible({ timeout: 10000 });
		await expect(page.getByText("Created")).toBeVisible();
		await expect(page.getByText("Updated")).toBeVisible();
		await expect(page.getByText(flow.id)).toBeVisible();
	});

	test("Flow runs with state badges on Runs tab", async ({
		page,
		apiClient,
	}) => {
		const flowName = `${TEST_PREFIX}runs-${Date.now()}`;
		const flow = await createFlow(apiClient, flowName);

		const completedRunName = `${TEST_PREFIX}run-a-${Date.now()}`;
		const failedRunName = `${TEST_PREFIX}run-b-${Date.now()}`;

		await createFlowRun(apiClient, {
			flowId: flow.id,
			name: completedRunName,
			state: { type: "COMPLETED", name: "Completed" },
		});
		await createFlowRun(apiClient, {
			flowId: flow.id,
			name: failedRunName,
			state: { type: "FAILED", name: "Failed" },
		});

		await page.goto(`/flows/flow/${flow.id}`);

		const runsTab = page.getByLabel("Runs");
		await expect(runsTab.getByText("Completed", { exact: true })).toBeVisible({
			timeout: 10000,
		});
		await expect(runsTab.getByText("Failed", { exact: true })).toBeVisible();
		await expect(page.getByText(completedRunName)).toBeVisible();
		await expect(page.getByText(failedRunName)).toBeVisible();
	});

	test("Activity chart cards", async ({ page, apiClient }) => {
		const flowName = `${TEST_PREFIX}charts-${Date.now()}`;
		const flow = await createFlow(apiClient, flowName);

		await createFlowRun(apiClient, {
			flowId: flow.id,
			name: `${TEST_PREFIX}chart-run-${Date.now()}`,
			state: { type: "COMPLETED", name: "Completed" },
		});

		await page.goto(`/flows/flow/${flow.id}`);

		await expect(page.getByText("Flow Runs").first()).toBeVisible({
			timeout: 10000,
		});
		await expect(page.getByText(/\d+ total/)).toBeVisible();
		await expect(page.getByText("Task Runs", { exact: true })).toBeVisible();
	});

	test("Deployments tab with deployment", async ({ page, apiClient }) => {
		const flowName = `${TEST_PREFIX}deploy-${Date.now()}`;
		const flow = await createFlow(apiClient, flowName);

		const deploymentName = `${TEST_PREFIX}dep-${Date.now()}`;
		await createDeployment(apiClient, {
			name: deploymentName,
			flowId: flow.id,
		});

		await page.goto(`/flows/flow/${flow.id}`);

		await page.getByRole("tab", { name: "Deployments" }).click();

		await expect(page).toHaveURL(/tab=deployments/);
		await expect(page.getByText(deploymentName)).toBeVisible({
			timeout: 10000,
		});
	});
});
