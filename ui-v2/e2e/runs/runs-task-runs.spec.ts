import type { Page } from "@playwright/test";
import {
	expect,
	runSimpleTask,
	type SimpleTaskResult,
	test,
	waitForServerHealth,
} from "../fixtures";

async function waitForTaskRunsTabReady(page: Page): Promise<void> {
	await expect(
		page
			.getByRole("heading", { name: /run a task or flow to get started/i })
			.or(page.getByText(/\d+ Task runs?/i)),
	).toBeVisible({ timeout: 10000 });
}

test.describe("Runs Page - Task Runs Tab", () => {
	test.describe.configure({ mode: "serial" });

	const prefix = "e2e-runs-tr-";
	let simpleTaskResult: SimpleTaskResult;

	test.beforeAll(async ({ apiClient }) => {
		await waitForServerHealth(apiClient);
		simpleTaskResult = runSimpleTask(prefix);
	});

	test("can deep-link to Task Runs tab via URL", async ({ page }) => {
		await page.goto("/runs?tab=task-runs");
		await waitForTaskRunsTabReady(page);

		const taskRunsTab = page.getByRole("tab", { name: "Task Runs" });
		await expect(taskRunsTab).toHaveAttribute("data-state", "active");

		await expect(page).toHaveURL(/tab=task-runs/);
	});

	test("displays task runs with name, state, and breadcrumb links", async ({
		page,
	}) => {
		const taskRunName = simpleTaskResult.task_run_names[0];
		const flowRunName = simpleTaskResult.flow_run_name;

		await expect(async () => {
			await page.goto("/runs?tab=task-runs");
			await expect(page.getByText(taskRunName)).toBeVisible({
				timeout: 2000,
			});
		}).toPass({ timeout: 15000 });

		const taskRunRow = page
			.getByRole("listitem")
			.filter({ has: page.getByRole("link", { name: taskRunName }) });
		await expect(taskRunRow.getByText("Completed")).toBeVisible();

		await expect(page.getByRole("link", { name: flowRunName })).toBeVisible();
	});

	test("can click task run to navigate to task run detail page", async ({
		page,
	}) => {
		const taskRunName = simpleTaskResult.task_run_names[0];

		await expect(async () => {
			await page.goto("/runs?tab=task-runs");
			await expect(page.getByText(taskRunName)).toBeVisible({
				timeout: 2000,
			});
		}).toPass({ timeout: 15000 });

		await page.getByRole("link", { name: taskRunName }).click();

		await expect(page).toHaveURL(/\/runs\/task-run\//, { timeout: 10000 });

		await expect(page.getByText(taskRunName)).toBeVisible({
			timeout: 10000,
		});
	});
});
