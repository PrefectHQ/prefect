import type { Page } from "@playwright/test";
import {
	cleanupWorkPools,
	createWorkPool,
	expect,
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
