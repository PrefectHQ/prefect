import type { Page } from "@playwright/test";
import {
	cleanupWorkPools,
	createWorkPool,
	expect,
	getWorkPool,
	listWorkPoolQueues,
	listWorkPools,
	test,
	waitForServerHealth,
} from "../fixtures";

const TEST_PREFIX = "e2e-wp-";

async function waitForWorkPoolsPageReady(page: Page): Promise<void> {
	await expect(
		page
			.getByRole("heading", { name: /add a work pool to get started/i })
			.or(page.getByText(/\d+ work pools?/i)),
	).toBeVisible({ timeout: 10000 });
}

test.describe("Work Pools List Page", () => {
	test.describe.configure({ mode: "serial" });

	test.beforeAll(async ({ apiClient }) => {
		await waitForServerHealth(apiClient);
	});

	test.beforeEach(async ({ apiClient }) => {
		try {
			await cleanupWorkPools(apiClient, TEST_PREFIX);
		} catch {
			// Ignore cleanup errors
		}
	});

	test.afterEach(async ({ apiClient }) => {
		try {
			await cleanupWorkPools(apiClient, TEST_PREFIX);
		} catch {
			// Ignore cleanup errors
		}
	});

	test("Empty state when no work pools exist", async ({ page, apiClient }) => {
		const pools = await listWorkPools(apiClient);
		test.skip(pools.length > 0, "Work pools already exist from other tests");

		await page.goto("/work-pools");
		await waitForWorkPoolsPageReady(page);

		await expect(
			page.getByRole("heading", { name: /add a work pool to get started/i }),
		).toBeVisible();
		await expect(
			page.getByRole("link", { name: /add work pool/i }),
		).toBeVisible();
	});

	test("Displays work pools in list with name and type", async ({
		page,
		apiClient,
	}) => {
		const timestamp = Date.now();
		const poolNameA = `${TEST_PREFIX}list-a-${timestamp}`;
		const poolNameB = `${TEST_PREFIX}list-b-${timestamp}`;

		await createWorkPool(apiClient, { name: poolNameA });
		await createWorkPool(apiClient, { name: poolNameB });

		await expect(async () => {
			await page.goto("/work-pools");
			await expect(page.getByRole("link", { name: poolNameA })).toBeVisible({
				timeout: 2000,
			});
		}).toPass({ timeout: 15000 });

		await expect(page.getByRole("link", { name: poolNameA })).toBeVisible();
		await expect(page.getByRole("link", { name: poolNameB })).toBeVisible();

		await expect(page.getByText(/\d+ work pools?/i)).toBeVisible();
	});

	test("Navigate to work pool detail from list", async ({
		page,
		apiClient,
	}) => {
		const timestamp = Date.now();
		const poolName = `${TEST_PREFIX}nav-${timestamp}`;

		await createWorkPool(apiClient, { name: poolName });

		await expect(async () => {
			await page.goto("/work-pools");
			await expect(page.getByRole("link", { name: poolName })).toBeVisible({
				timeout: 2000,
			});
		}).toPass({ timeout: 15000 });

		await page.getByRole("link", { name: poolName }).click();

		await expect(page).toHaveURL(
			new RegExp(`/work-pools/work-pool/${poolName}`),
			{ timeout: 10000 },
		);
		await expect(page.getByText(poolName)).toBeVisible();
	});
});

test.describe("Work Pool Detail Page", () => {
	test.describe.configure({ mode: "serial" });

	test.beforeAll(async ({ apiClient }) => {
		await waitForServerHealth(apiClient);
	});

	test.beforeEach(async ({ apiClient }) => {
		try {
			await cleanupWorkPools(apiClient, TEST_PREFIX);
		} catch {
			// Ignore cleanup errors
		}
	});

	test.afterEach(async ({ apiClient }) => {
		try {
			await cleanupWorkPools(apiClient, TEST_PREFIX);
		} catch {
			// Ignore cleanup errors
		}
	});

	test("View work pool detail metadata", async ({ page, apiClient }) => {
		const poolName = `${TEST_PREFIX}detail-${Date.now()}`;
		await createWorkPool(apiClient, {
			name: poolName,
			description: "Test description for detail",
		});

		await page.goto(`/work-pools/work-pool/${poolName}`);

		await expect(page.getByText(poolName)).toBeVisible({ timeout: 10000 });

		await expect(
			page.getByLabel("breadcrumb").getByText(poolName),
		).toBeVisible();

		await expect(page.getByText("process")).toBeVisible();

		await expect(page.getByText("Test description for detail")).toBeVisible();
	});

	test("View work queues tab with default queue", async ({
		page,
		apiClient,
	}) => {
		const poolName = `${TEST_PREFIX}queues-${Date.now()}`;
		await createWorkPool(apiClient, { name: poolName });

		await page.goto(`/work-pools/work-pool/${poolName}`);

		await expect(page.getByText(poolName)).toBeVisible({ timeout: 10000 });

		await page.getByRole("tab", { name: /work queues/i }).click();

		await expect(page.getByRole("link", { name: "default" })).toBeVisible({
			timeout: 10000,
		});

		const queues = await listWorkPoolQueues(apiClient, poolName);
		expect(queues.length).toBeGreaterThanOrEqual(1);
		expect(queues.some((q) => q.name === "default")).toBe(true);
	});

	test("Navigate to work queue details from work pool", async ({
		page,
		apiClient,
	}) => {
		const poolName = `${TEST_PREFIX}queue-nav-${Date.now()}`;
		await createWorkPool(apiClient, { name: poolName });

		await page.goto(`/work-pools/work-pool/${poolName}`);

		await expect(page.getByText(poolName)).toBeVisible({ timeout: 10000 });

		await page.getByRole("tab", { name: /work queues/i }).click();

		await expect(page.getByRole("link", { name: "default" })).toBeVisible({
			timeout: 10000,
		});

		await page.getByRole("link", { name: "default" }).click();

		await expect(page).toHaveURL(/queue\/default/, {
			timeout: 10000,
		});

		await expect(page.getByText("default")).toBeVisible();
	});
});

test.describe("Work Pool Actions", () => {
	test.describe.configure({ mode: "serial" });

	test.beforeAll(async ({ apiClient }) => {
		await waitForServerHealth(apiClient);
	});

	test.beforeEach(async ({ apiClient }) => {
		try {
			await cleanupWorkPools(apiClient, TEST_PREFIX);
		} catch {
			// Ignore cleanup errors
		}
	});

	test.afterEach(async ({ apiClient }) => {
		try {
			await cleanupWorkPools(apiClient, TEST_PREFIX);
		} catch {
			// Ignore cleanup errors
		}
	});

	test("Create work pool via wizard (process type)", async ({
		page,
		apiClient,
	}) => {
		const poolName = `${TEST_PREFIX}create-${Date.now()}`;

		await page.goto("/work-pools/create");

		await expect(
			page
				.getByRole("radio", { name: /process/i })
				.or(page.getByLabel("Process"))
				.or(page.locator("label").filter({ hasText: "Process" })),
		).toBeVisible({ timeout: 10000 });

		await page
			.getByRole("radio", { name: /process/i })
			.or(page.getByLabel("Process"))
			.or(page.locator("label").filter({ hasText: "Process" }))
			.click();

		await page.getByRole("button", { name: /next/i }).click();

		await page.getByLabel("Name").fill(poolName);

		await page.getByRole("button", { name: /next/i }).click();

		await page.getByRole("button", { name: /create work pool/i }).click();

		await expect(page).toHaveURL(
			new RegExp(`/work-pools/work-pool/${poolName}`),
			{ timeout: 10000 },
		);

		await expect(page.getByText(poolName)).toBeVisible({ timeout: 10000 });

		await expect
			.poll(
				async () => {
					const pools = await listWorkPools(apiClient);
					return pools.some((p) => p.name === poolName);
				},
				{ timeout: 10000 },
			)
			.toBe(true);
	});

	test("Toggle work pool pause/resume", async ({ page, apiClient }) => {
		const poolName = `${TEST_PREFIX}toggle-${Date.now()}`;
		await createWorkPool(apiClient, { name: poolName });

		await page.goto(`/work-pools/work-pool/${poolName}`);

		await expect(page.getByText(poolName)).toBeVisible({ timeout: 10000 });

		await page.getByRole("switch").click();

		await expect
			.poll(
				async () => {
					const pool = await getWorkPool(apiClient, poolName);
					return pool.is_paused;
				},
				{ timeout: 10000 },
			)
			.toBe(true);

		await page.getByRole("switch").click();

		await expect
			.poll(
				async () => {
					const pool = await getWorkPool(apiClient, poolName);
					return pool.is_paused;
				},
				{ timeout: 10000 },
			)
			.toBe(false);
	});

	test("Delete work pool via action menu", async ({ page, apiClient }) => {
		const poolName = `${TEST_PREFIX}delete-${Date.now()}`;
		await createWorkPool(apiClient, { name: poolName });

		await page.goto(`/work-pools/work-pool/${poolName}`);

		await expect(page.getByText(poolName)).toBeVisible({ timeout: 10000 });

		const moreButton = page
			.getByRole("button")
			.filter({ has: page.locator(".lucide-ellipsis-vertical") });
		await moreButton.click();

		await page.getByRole("menuitem", { name: /delete/i }).click();

		const dialog = page.getByRole("alertdialog");
		await expect(dialog).toBeVisible();

		await dialog.getByRole("textbox").fill(poolName);
		await dialog.getByRole("button", { name: /delete/i }).click();

		await expect(page).toHaveURL(/\/work-pools/, { timeout: 10000 });

		await expect
			.poll(
				async () => {
					const pools = await listWorkPools(apiClient);
					return pools.some((p) => p.name === poolName);
				},
				{ timeout: 10000 },
			)
			.toBe(false);
	});
});
