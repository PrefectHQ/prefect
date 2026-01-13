import {
	cleanupGlobalConcurrencyLimits,
	cleanupTaskRunConcurrencyLimits,
	expect,
	listGlobalConcurrencyLimits,
	listTaskRunConcurrencyLimits,
	test,
	waitForServerHealth,
} from "../fixtures";

const TEST_PREFIX = "e2e-test-";

test.describe("Concurrency Limits Page", () => {
	test.beforeAll(async ({ apiClient }) => {
		await waitForServerHealth(apiClient);
	});

	test.beforeEach(async ({ apiClient }) => {
		await cleanupGlobalConcurrencyLimits(apiClient, TEST_PREFIX);
		await cleanupTaskRunConcurrencyLimits(apiClient, TEST_PREFIX);
	});

	test.afterEach(async ({ apiClient }) => {
		await cleanupGlobalConcurrencyLimits(apiClient, TEST_PREFIX);
		await cleanupTaskRunConcurrencyLimits(apiClient, TEST_PREFIX);
	});

	test("Global Concurrency Limits - CRUD flow", async ({ page, apiClient }) => {
		const limitName = `${TEST_PREFIX}global-limit-${Date.now()}`;

		await page.goto("/concurrency-limits?tab=global");

		// Verify empty state
		await expect(
			page.getByRole("heading", { name: /add a concurrency limit/i }),
		).toBeVisible();

		// Create
		await page.getByRole("button", { name: /add concurrency limit/i }).click();
		await expect(
			page.getByRole("dialog", { name: /add concurrency limit/i }),
		).toBeVisible();
		await page.getByRole("textbox", { name: /name/i }).fill(limitName);
		await page
			.getByRole("spinbutton", { name: /concurrency limit/i })
			.fill("5");
		await page.getByRole("button", { name: /save/i }).click();
		await expect(page.getByRole("dialog")).not.toBeVisible();
		await expect(page.getByText(limitName)).toBeVisible();

		// Verify create via API
		let limits = await listGlobalConcurrencyLimits(apiClient);
		const created = limits.find((l) => l.name === limitName);
		expect(created?.limit).toBe(5);

		// Edit
		await page.getByRole("button", { name: /open menu/i }).click();
		await page.getByRole("menuitem", { name: /edit/i }).click();
		await expect(
			page.getByRole("dialog", {
				name: new RegExp(`update ${limitName}`, "i"),
			}),
		).toBeVisible();
		await page
			.getByRole("spinbutton", { name: /concurrency limit/i })
			.fill("10");
		await page.getByRole("button", { name: /update/i }).click();
		await expect(page.getByRole("dialog")).not.toBeVisible();

		// Verify edit via API
		limits = await listGlobalConcurrencyLimits(apiClient);
		expect(limits.find((l) => l.name === limitName)?.limit).toBe(10);

		// Toggle active
		const activeSwitch = page.getByRole("switch", { name: /toggle active/i });
		await expect(activeSwitch).toBeChecked();
		await activeSwitch.click();
		await expect(activeSwitch).not.toBeChecked();

		// Verify toggle via API
		limits = await listGlobalConcurrencyLimits(apiClient);
		expect(limits.find((l) => l.name === limitName)?.active).toBe(false);

		// Delete
		await page.getByRole("button", { name: /open menu/i }).click();
		await page.getByRole("menuitem", { name: /delete/i }).click();
		await expect(
			page.getByRole("dialog", { name: /delete concurrency limit/i }),
		).toBeVisible();
		await page.getByRole("button", { name: /delete/i }).click();
		await expect(page.getByText(limitName)).not.toBeVisible();

		// Verify empty state returns
		await expect(
			page.getByRole("heading", { name: /add a concurrency limit/i }),
		).toBeVisible();

		// Verify delete via API
		limits = await listGlobalConcurrencyLimits(apiClient);
		expect(limits.find((l) => l.name === limitName)).toBeUndefined();
	});

	test("Task Run Concurrency Limits - CRUD flow", async ({
		page,
		apiClient,
	}) => {
		const tagName = `${TEST_PREFIX}task-tag-${Date.now()}`;

		await page.goto("/concurrency-limits?tab=task-run");

		// Verify empty state
		await expect(
			page.getByRole("heading", {
				name: /add a concurrency limit for your task runs/i,
			}),
		).toBeVisible();

		// Create
		await page.getByRole("button", { name: /add concurrency limit/i }).click();
		await expect(
			page.getByRole("dialog", { name: /add task run concurrency limit/i }),
		).toBeVisible();
		await page.getByRole("textbox", { name: /tag/i }).fill(tagName);
		await page
			.getByRole("spinbutton", { name: /concurrency limit/i })
			.fill("10");
		await page.getByRole("button", { name: /^add$/i }).click();
		await expect(page.getByRole("dialog")).not.toBeVisible();
		await expect(page.getByText(tagName)).toBeVisible();

		// Verify create via API
		let limits = await listTaskRunConcurrencyLimits(apiClient);
		expect(limits.find((l) => l.tag === tagName)?.concurrency_limit).toBe(10);

		// Reset
		await page.getByRole("button", { name: /open menu/i }).click();
		await page.getByRole("menuitem", { name: /reset/i }).click();
		await expect(
			page.getByRole("dialog", { name: new RegExp(`reset.*${tagName}`, "i") }),
		).toBeVisible();
		await page.getByRole("button", { name: /reset/i }).click();
		await expect(page.getByRole("dialog")).not.toBeVisible();
		await expect(page.getByText(tagName)).toBeVisible(); // Still exists after reset

		// Delete
		await page.getByRole("button", { name: /open menu/i }).click();
		await page.getByRole("menuitem", { name: /delete/i }).click();
		await expect(
			page.getByRole("dialog", { name: /delete concurrency limit/i }),
		).toBeVisible();
		await page.getByRole("button", { name: /delete/i }).click();
		await expect(page.getByText(tagName)).not.toBeVisible();

		// Verify empty state returns
		await expect(
			page.getByRole("heading", {
				name: /add a concurrency limit for your task runs/i,
			}),
		).toBeVisible();

		// Verify delete via API
		limits = await listTaskRunConcurrencyLimits(apiClient);
		expect(limits.find((l) => l.tag === tagName)).toBeUndefined();
	});

	test("Tab navigation", async ({ page }) => {
		await page.goto("/concurrency-limits");

		// Default is Global tab
		await expect(page.getByRole("tab", { name: /global/i })).toHaveAttribute(
			"aria-selected",
			"true",
		);
		await expect(page).toHaveURL(/tab=global/);

		// Switch to Task Run tab
		await page.getByRole("tab", { name: /task run/i }).click();
		await expect(page.getByRole("tab", { name: /task run/i })).toHaveAttribute(
			"aria-selected",
			"true",
		);
		await expect(page).toHaveURL(/tab=task-run/);

		// Switch back to Global tab
		await page.getByRole("tab", { name: /global/i }).click();
		await expect(page.getByRole("tab", { name: /global/i })).toHaveAttribute(
			"aria-selected",
			"true",
		);
		await expect(page).toHaveURL(/tab=global/);
	});
});
