import {
	cleanupFlowRuns,
	cleanupFlows,
	expect,
	runSimpleTask,
	test,
	waitForServerHealth,
} from "../fixtures";

const TEST_PREFIX = "e2e-trun-detail-";

test.describe("Task Run Detail Page", () => {
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

	test("Navigate to task run detail by ID", async ({ page }) => {
		const result = runSimpleTask(TEST_PREFIX);
		const taskRunId = result.task_run_ids[0];
		const taskRunName = result.task_run_names[0];

		await page.goto(`/runs/task-run/${taskRunId}`);

		await expect(page.getByText(taskRunName, { exact: true })).toBeVisible({
			timeout: 15000,
		});
		await expect(page).toHaveURL(new RegExp(`/runs/task-run/${taskRunId}`));
	});

	test("Task run metadata with parent flow run link", async ({ page }) => {
		const result = runSimpleTask(TEST_PREFIX);
		const taskRunId = result.task_run_ids[0];

		await page.goto(`/runs/task-run/${taskRunId}`);

		await expect(
			page.getByText(result.task_run_names[0], { exact: true }),
		).toBeVisible({ timeout: 15000 });

		const badge = page.locator('[class*="bg-state-completed"]');
		await expect(badge).toBeVisible({ timeout: 10000 });
		await expect(badge.getByText("Completed")).toBeVisible();

		const parentLink = page.getByRole("link", {
			name: result.flow_run_name,
		});
		await expect(parentLink).toBeVisible({ timeout: 10000 });
		await parentLink.click();

		await expect(page).toHaveURL(
			new RegExp(`/runs/flow-run/${result.flow_run_id}`),
		);
		await expect(
			page.getByText(result.flow_run_name, { exact: true }),
		).toBeVisible({ timeout: 10000 });
	});

	test("Task run detail sidebar shows metadata", async ({ page }) => {
		const result = runSimpleTask(TEST_PREFIX);
		const taskRunId = result.task_run_ids[0];

		await page.goto(`/runs/task-run/${taskRunId}`);

		await expect(
			page.getByText(result.task_run_names[0], { exact: true }),
		).toBeVisible({ timeout: 15000 });

		await expect(page.getByText("Flow Run")).toBeVisible({ timeout: 10000 });

		const hasTiming = await Promise.race([
			page
				.getByText("Start Time")
				.isVisible()
				.then((v) => v),
			page
				.getByText("Duration")
				.isVisible()
				.then((v) => v),
		]);
		expect(hasTiming).toBe(true);
	});
});
