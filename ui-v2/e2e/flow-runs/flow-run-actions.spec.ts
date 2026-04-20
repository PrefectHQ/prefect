import {
	cleanupFlowRuns,
	cleanupFlows,
	createFlow,
	createFlowRun,
	createLogs,
	expect,
	listFlowRuns,
	test,
	waitForServerHealth,
} from "../fixtures";

const TEST_PREFIX = "e2e-frun-actions-";

test.describe("Flow Run Actions", () => {
	test.describe.configure({ mode: "serial" });

	test.beforeAll(async ({ apiClient }) => {
		await waitForServerHealth(apiClient);
	});

	test.beforeEach(async ({ apiClient }) => {
		try {
			await cleanupFlowRuns(apiClient, TEST_PREFIX);
			await cleanupFlows(apiClient, TEST_PREFIX);
		} catch {
			// Ignore cleanup errors
		}
	});

	test.afterEach(async ({ apiClient }) => {
		try {
			await cleanupFlowRuns(apiClient, TEST_PREFIX);
			await cleanupFlows(apiClient, TEST_PREFIX);
		} catch {
			// Ignore cleanup errors
		}
	});

	test("View logs tab with log entries", async ({ page, apiClient }) => {
		const flowName = `${TEST_PREFIX}logs-${Date.now()}`;
		const flow = await createFlow(apiClient, flowName);
		const runName = `${TEST_PREFIX}logs-run-${Date.now()}`;
		const flowRun = await createFlowRun(apiClient, {
			flowId: flow.id,
			name: runName,
			state: { type: "COMPLETED", name: "Completed" },
		});

		await createLogs(apiClient, {
			flowRunId: flowRun.id,
			logs: [
				{ message: "Starting flow execution" },
				{ message: "Processing data batch" },
				{ message: "Flow completed successfully" },
			],
		});

		await page.goto(`/runs/flow-run/${flowRun.id}`);

		await expect(page.getByText(runName, { exact: true })).toBeVisible({
			timeout: 10000,
		});

		await expect(page.getByText("Starting flow execution")).toBeVisible({
			timeout: 10000,
		});

		await expect(
			page.locator("time, [datetime], .text-muted-foreground").first(),
		).toBeVisible({ timeout: 10000 });
	});

	test("Delete flow run via action menu with confirmation", async ({
		page,
		apiClient,
	}) => {
		const flowName = `${TEST_PREFIX}delete-${Date.now()}`;
		const flow = await createFlow(apiClient, flowName);
		const runName = `${TEST_PREFIX}delete-run-${Date.now()}`;
		const flowRun = await createFlowRun(apiClient, {
			flowId: flow.id,
			name: runName,
			state: { type: "COMPLETED", name: "Completed" },
		});

		await page.goto(`/runs/flow-run/${flowRun.id}`);

		await expect(page.getByText(runName, { exact: true })).toBeVisible({
			timeout: 10000,
		});

		const moreButton = page
			.getByRole("button")
			.filter({ has: page.locator(".lucide-ellipsis-vertical") });
		await moreButton.click();

		await page.getByRole("menuitem", { name: "Delete" }).click();

		await page
			.getByRole("alertdialog")
			.getByRole("button", { name: "Delete" })
			.click();

		await expect(page).toHaveURL(/\/runs/, { timeout: 10000 });

		const deletedId = flowRun.id;
		await expect
			.poll(
				async () => {
					const runs = await listFlowRuns(apiClient);
					return runs.some((r) => r.id === deletedId);
				},
				{ timeout: 10000 },
			)
			.toBe(false);
	});
});
