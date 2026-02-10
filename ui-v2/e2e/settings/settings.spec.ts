import { expect, test, waitForServerHealth } from "../fixtures";

test.describe("Settings Page", () => {
	test.beforeAll(async ({ apiClient }) => {
		await waitForServerHealth(apiClient);
	});

	test("should navigate to settings page and see all sections (SETT-01, SETT-02)", async ({
		page,
	}) => {
		await page.goto("/settings");

		await expect(
			page.getByLabel("breadcrumb").getByText("Settings"),
		).toBeVisible();
		await expect(page.getByText("Version")).toBeVisible();
		await expect(page.getByText("Theme")).toBeVisible();
		await expect(page.locator("label[for='light']")).toBeVisible();
		await expect(page.locator("label[for='dark']")).toBeVisible();
		await expect(page.locator("label[for='system']")).toBeVisible();
		await expect(page.getByText("Color Mode")).toBeVisible();
		await expect(page.getByText("Server Settings")).toBeVisible();
	});

	test("should toggle theme to dark and persist after reload (SETT-03)", async ({
		page,
	}) => {
		await page.goto("/settings");

		await page.locator("label[for='dark']").click();
		await expect(page.locator("html")).toHaveClass(/dark/);

		await page.reload();
		await expect(
			page.getByLabel("breadcrumb").getByText("Settings"),
		).toBeVisible();
		await expect(page.locator("html")).toHaveClass(/dark/);

		await page.locator("label[for='system']").click();
	});

	test("should toggle theme to light and persist after reload (SETT-03)", async ({
		page,
	}) => {
		await page.goto("/settings");

		await page.locator("label[for='light']").click();
		await expect(page.locator("html")).not.toHaveClass(/dark/);

		await page.reload();
		await expect(
			page.getByLabel("breadcrumb").getByText("Settings"),
		).toBeVisible();
		await expect(page.locator("html")).not.toHaveClass(/dark/);

		await page.locator("label[for='system']").click();
	});
});
