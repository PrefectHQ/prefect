import { expect, test, waitForServerHealth } from "../fixtures";

test.describe("Settings Page", () => {
	test.beforeAll(async ({ apiClient }) => {
		await waitForServerHealth(apiClient);
	});

	test("should navigate to settings page and see all sections (SETT-01, SETT-02)", async ({
		page,
	}) => {
		await page.goto("/settings");

		await expect(page.getByText("Settings")).toBeVisible();
		await expect(page.getByText("Version")).toBeVisible();
		await expect(page.getByText("Theme")).toBeVisible();
		await expect(page.getByLabel("Light")).toBeVisible();
		await expect(page.getByLabel("Dark")).toBeVisible();
		await expect(page.getByLabel("System")).toBeVisible();
		await expect(page.getByText("Color Mode")).toBeVisible();
		await expect(page.getByText("Server Settings")).toBeVisible();
	});

	test("should toggle theme to dark and persist after reload (SETT-03)", async ({
		page,
	}) => {
		await page.goto("/settings");

		await page.getByLabel("Dark").click();
		await expect(page.locator("html")).toHaveClass(/dark/);

		await page.reload();
		await expect(page.getByText("Settings")).toBeVisible();
		await expect(page.locator("html")).toHaveClass(/dark/);

		await page.getByLabel("System").click();
	});

	test("should toggle theme to light and persist after reload (SETT-03)", async ({
		page,
	}) => {
		await page.goto("/settings");

		await page.getByLabel("Light").click();
		await expect(page.locator("html")).not.toHaveClass(/dark/);

		await page.reload();
		await expect(page.getByText("Settings")).toBeVisible();
		await expect(page.locator("html")).not.toHaveClass(/dark/);

		await page.getByLabel("System").click();
	});
});
