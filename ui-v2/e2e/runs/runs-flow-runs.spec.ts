import type { Page } from "@playwright/test";
import {
	cleanupFlowRuns,
	cleanupFlows,
	createFlow,
	createFlowRun,
	expect,
	type ParentChildResult,
	runParentChild,
	test,
	waitForServerHealth,
} from "../fixtures";

type ApiClient = Parameters<typeof createFlowRun>[0];
type CreateFlowRunParams = Parameters<typeof createFlowRun>[1];

async function createFlowRunWithRetry(
	client: ApiClient,
	params: CreateFlowRunParams,
): Promise<void> {
	await expect(async () => {
		await createFlowRun(client, params);
	}).toPass({ timeout: 30000 });
}

async function waitForRunsPageReady(page: Page): Promise<void> {
	await expect(
		page
			.getByRole("heading", { name: /run a task or flow to get started/i })
			.or(page.getByText(/\d+ Flow runs?/i)),
	).toBeVisible({ timeout: 10000 });
}

test.describe("Runs Page - Tab Switching", () => {
	test.describe.configure({ mode: "serial" });

	const prefix = "e2e-runs-tab-";
	const timestamp = Date.now();

	test.beforeAll(async ({ apiClient }) => {
		await waitForServerHealth(apiClient);
		const flow = await createFlow(apiClient, `${prefix}flow-${timestamp}`);
		const flowId = flow.id;
		for (let i = 0; i < 6; i++) {
			await createFlowRunWithRetry(apiClient, {
				flowId,
				name: `${prefix}run-${timestamp}-${String(i).padStart(2, "0")}`,
				state: i < 3 ? { type: "COMPLETED" } : { type: "FAILED" },
			});
		}
	});

	test.afterAll(async ({ apiClient }) => {
		try {
			await cleanupFlowRuns(apiClient, prefix);
			await cleanupFlows(apiClient, prefix);
		} catch {
			// Ignore cleanup errors
		}
	});

	test("can switch between Flow Runs and Task Runs tabs with URL updates and filter persistence", async ({
		page,
	}) => {
		await expect(async () => {
			await page.goto(
				`/runs?limit=5&flow-run-search=${encodeURIComponent(`${prefix}run-${timestamp}`)}`,
			);
			await expect(page.getByText(/\d+ Flow runs?/i)).toBeVisible({
				timeout: 2000,
			});
		}).toPass({ timeout: 15000 });

		await expect(page.getByRole("tab", { name: /flow runs/i })).toBeVisible();

		const stateFilterButton = page.getByRole("button", {
			name: /all run states/i,
		});
		await stateFilterButton.click();
		await page.getByRole("menuitem", { name: "Completed" }).click();
		await page.keyboard.press("Escape");

		await expect(page).toHaveURL(/state=Completed/);

		const nextPageButton = page.getByRole("button", {
			name: /go to next page/i,
		});
		if (await nextPageButton.isEnabled({ timeout: 3000 }).catch(() => false)) {
			await nextPageButton.click();
			await expect(page).toHaveURL(/page=2/);
		}

		await page.getByRole("tab", { name: /task runs/i }).click();
		await expect(page).toHaveURL(/tab=task-runs/);
		await expect(page).toHaveURL(/state=Completed/);
		await expect(page).not.toHaveURL(/page=2/);

		await page.getByRole("tab", { name: /flow runs/i }).click();
		await expect(page).toHaveURL(/state=Completed/);
	});
});

test.describe("Runs Page - Flow Runs List & Filters", () => {
	test.describe.configure({ mode: "serial" });

	const prefix = "e2e-runs-fr-";
	const timestamp = Date.now();
	let parentChildResult: ParentChildResult;

	test.beforeAll(async ({ apiClient }) => {
		await waitForServerHealth(apiClient);

		const flow = await createFlow(apiClient, `${prefix}flow-${timestamp}`);
		const flowId = flow.id;

		for (let i = 0; i < 12; i++) {
			let stateType: "COMPLETED" | "FAILED" | "CANCELLED";
			if (i < 4) stateType = "COMPLETED";
			else if (i < 8) stateType = "FAILED";
			else stateType = "CANCELLED";

			await createFlowRunWithRetry(apiClient, {
				flowId,
				name: `${prefix}run-${timestamp}-${String(i).padStart(2, "0")}`,
				state: { type: stateType },
			});
		}

		parentChildResult = runParentChild(`${prefix}pc-`);
	});

	test.afterAll(async ({ apiClient }) => {
		try {
			await cleanupFlowRuns(apiClient, prefix);
			await cleanupFlows(apiClient, prefix);
		} catch {
			// Ignore cleanup errors
		}
	});

	test("displays flow runs with state, name, and timestamps", async ({
		page,
	}) => {
		await expect(async () => {
			await page.goto(
				`/runs?flow-run-search=${encodeURIComponent(`${prefix}run-${timestamp}`)}`,
			);
			await expect(
				page.getByText(new RegExp(`${prefix}run-${timestamp}-\\d{2}`)).first(),
			).toBeVisible({ timeout: 2000 });
		}).toPass({ timeout: 15000 });

		await expect(page.getByText("Completed").first()).toBeVisible();
		await expect(page.getByText("Failed").first()).toBeVisible();
	});

	test("filters by state with URL persistence", async ({ page }) => {
		await expect(async () => {
			await page.goto(
				`/runs?flow-run-search=${encodeURIComponent(`${prefix}run-${timestamp}`)}`,
			);
			await expect(
				page.getByText(new RegExp(`${prefix}run-${timestamp}-\\d{2}`)).first(),
			).toBeVisible({ timeout: 2000 });
		}).toPass({ timeout: 15000 });

		const stateFilterButton = page.getByRole("button", {
			name: /all run states/i,
		});
		await stateFilterButton.click();
		await page.getByRole("menuitem", { name: "Failed" }).click();
		await page.keyboard.press("Escape");

		await expect(page).toHaveURL(/state=Failed/);

		const failedRunName = `${prefix}run-${timestamp}-04`;
		const completedRunName = `${prefix}run-${timestamp}-00`;

		await expect(page.getByText(failedRunName)).toBeVisible({
			timeout: 10000,
		});
		await expect(page.getByText(completedRunName)).not.toBeVisible({
			timeout: 10000,
		});

		await page.reload();
		await expect(page).toHaveURL(/state=Failed/);
		await expect(page.getByText(failedRunName)).toBeVisible({
			timeout: 10000,
		});
		await expect(page.getByText(completedRunName)).not.toBeVisible({
			timeout: 10000,
		});
	});

	test("searches by name with full URL persistence cycle", async ({ page }) => {
		await page.goto("/runs");
		await waitForRunsPageReady(page);

		const searchInput = page.getByRole("textbox", {
			name: /search by flow run name/i,
		});
		const searchValue = `${prefix}run-${timestamp}`;
		await searchInput.fill(searchValue);

		await expect(page).toHaveURL(
			new RegExp(`flow-run-search=${encodeURIComponent(searchValue)}`),
			{ timeout: 5000 },
		);

		await expect(
			page.getByText(new RegExp(`${prefix}run-${timestamp}-\\d{2}`)).first(),
		).toBeVisible({ timeout: 10000 });

		await page.reload();
		await waitForRunsPageReady(page);
		await expect(page).toHaveURL(
			new RegExp(`flow-run-search=${encodeURIComponent(searchValue)}`),
		);
		await expect(searchInput).toHaveValue(searchValue, { timeout: 10000 });

		await searchInput.clear();
		await expect(page).not.toHaveURL(
			new RegExp(`flow-run-search=${encodeURIComponent(searchValue)}`),
			{ timeout: 5000 },
		);
	});

	test("paginates through flow runs with URL updates", async ({ page }) => {
		await expect(async () => {
			await page.goto(
				`/runs?limit=5&flow-run-search=${encodeURIComponent(`${prefix}run-${timestamp}`)}`,
			);
			await expect(page.getByText(/Page 1 of/)).toBeVisible({
				timeout: 2000,
			});
		}).toPass({ timeout: 15000 });

		await page.getByRole("button", { name: /go to next page/i }).click();

		await expect(page).toHaveURL(/page=2/);
		await expect(page.getByText(/Page 2 of/)).toBeVisible();
	});

	test("toggles hide subflows with URL persistence", async ({ page }) => {
		const parentName = parentChildResult.parent_flow_run_name;
		const childName = parentChildResult.child_flow_run_name;

		await expect(async () => {
			await page.goto(
				`/runs?flow-run-search=${encodeURIComponent(`${prefix}pc-`)}`,
			);
			await expect(page.getByText(parentName)).toBeVisible({
				timeout: 2000,
			});
		}).toPass({ timeout: 15000 });

		await expect(page.getByText(childName)).toBeVisible({
			timeout: 10000,
		});

		await page.getByRole("switch", { name: /hide subflows/i }).click();

		await expect(page).toHaveURL(/hide-subflows=true/);
		await expect(page.getByText(childName)).not.toBeVisible({
			timeout: 10000,
		});
		await expect(page.getByText(parentName)).toBeVisible();

		await page.reload();
		await expect(page).toHaveURL(/hide-subflows=true/);
		await expect(page.getByText(parentName)).toBeVisible({
			timeout: 10000,
		});
		await expect(page.getByText(childName)).not.toBeVisible({
			timeout: 10000,
		});
	});

	test("selects preset date range filter", async ({ page }) => {
		await page.goto(
			`/runs?flow-run-search=${encodeURIComponent(`${prefix}run-${timestamp}`)}`,
		);
		await waitForRunsPageReady(page);

		await expect(async () => {
			const clearDateRange = page.getByRole("button", {
				name: /clear date range/i,
			});
			if (await clearDateRange.isVisible()) {
				await clearDateRange.click();
			}
			await expect(page.getByRole("button", { name: /all time/i })).toBeVisible(
				{ timeout: 2000 },
			);
		}).toPass({ timeout: 10000 });

		await page.getByRole("button", { name: /all time/i }).click();

		await page.getByRole("button", { name: "Past 7 days" }).click();

		await expect(page).toHaveURL(/range=past-7-days/);

		await expect(
			page.getByText(new RegExp(`${prefix}run-${timestamp}-\\d{2}`)).first(),
		).toBeVisible({ timeout: 10000 });
	});

	test("applies custom date range via URL", async ({ page }) => {
		const now = new Date();
		const start = new Date(
			now.getTime() - 7 * 24 * 60 * 60 * 1000,
		).toISOString();
		const end = now.toISOString();

		await expect(async () => {
			await page.goto(
				`/runs?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}&flow-run-search=${encodeURIComponent(`${prefix}run-${timestamp}`)}`,
			);
			await expect(
				page.getByText(new RegExp(`${prefix}run-${timestamp}-\\d{2}`)).first(),
			).toBeVisible({ timeout: 2000 });
		}).toPass({ timeout: 15000 });
	});

	test("combines state + name filters", async ({ page }) => {
		await expect(async () => {
			await page.goto(
				`/runs?flow-run-search=${encodeURIComponent(`${prefix}run-${timestamp}`)}`,
			);
			await expect(
				page.getByText(new RegExp(`${prefix}run-${timestamp}-\\d{2}`)).first(),
			).toBeVisible({ timeout: 2000 });
		}).toPass({ timeout: 15000 });

		const stateFilterButton = page.getByRole("button", {
			name: /all run states/i,
		});
		await stateFilterButton.click();
		await page.getByRole("menuitem", { name: "Completed" }).click();
		await page.keyboard.press("Escape");

		await expect(page).toHaveURL(/state=Completed/);
		await expect(page).toHaveURL(/flow-run-search=/);

		const completedRunName = `${prefix}run-${timestamp}-00`;
		const failedRunName = `${prefix}run-${timestamp}-04`;

		await expect(page.getByText(completedRunName)).toBeVisible({
			timeout: 10000,
		});
		await expect(page.getByText(failedRunName)).not.toBeVisible({
			timeout: 10000,
		});

		await page.reload();
		await expect(page).toHaveURL(/state=Completed/);
		await expect(page).toHaveURL(/flow-run-search=/);
		await expect(page.getByText(completedRunName)).toBeVisible({
			timeout: 10000,
		});
	});

	test("combines name + hide-subflows filters", async ({ page }) => {
		const parentName = parentChildResult.parent_flow_run_name;
		const childName = parentChildResult.child_flow_run_name;

		await expect(async () => {
			await page.goto(
				`/runs?flow-run-search=${encodeURIComponent(`${prefix}pc-`)}`,
			);
			await expect(page.getByText(parentName)).toBeVisible({
				timeout: 2000,
			});
		}).toPass({ timeout: 15000 });

		await page.getByRole("switch", { name: /hide subflows/i }).click();

		await expect(page).toHaveURL(/flow-run-search=/);
		await expect(page).toHaveURL(/hide-subflows=true/);
		await expect(page.getByText(childName)).not.toBeVisible({
			timeout: 10000,
		});
		await expect(page.getByText(parentName)).toBeVisible();
	});

	test("combines state + date range filters", async ({ page }) => {
		await expect(async () => {
			await page.goto(
				`/runs?flow-run-search=${encodeURIComponent(`${prefix}run-${timestamp}`)}&state=Completed&range=past-7-days`,
			);
			await expect(
				page.getByText(new RegExp(`${prefix}run-${timestamp}-\\d{2}`)).first(),
			).toBeVisible({ timeout: 2000 });
		}).toPass({ timeout: 15000 });

		await expect(page).toHaveURL(/state=Completed/);
		await expect(page).toHaveURL(/range=past-7-days/);

		const completedRunName = `${prefix}run-${timestamp}-00`;
		const failedRunName = `${prefix}run-${timestamp}-04`;

		await expect(page.getByText(completedRunName)).toBeVisible({
			timeout: 10000,
		});
		await expect(page.getByText(failedRunName)).not.toBeVisible({
			timeout: 10000,
		});
	});
});
