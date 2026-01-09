import { expect, isAuthRequired, test, waitForServerHealth } from "../fixtures";

const TEST_CREDENTIALS = "admin:secret";

test.describe("Auth Smoke Test", () => {
	test.beforeAll(async ({ apiClient }) => {
		await waitForServerHealth(apiClient);
	});

	test("should complete the full login flow when auth is enabled", async ({
		page,
		apiClient,
	}) => {
		const authRequired = await isAuthRequired(apiClient);
		test.skip(!authRequired, "Auth is not enabled on this server");

		// Navigate to a protected route (dashboard)
		await page.goto("/dashboard");

		// Should be redirected to login page
		await expect(page).toHaveURL(/\/login/);

		// Verify login form is visible
		await expect(page.getByRole("heading", { name: /login/i })).toBeVisible();

		// Enter credentials
		await page.getByPlaceholder("admin:pass").fill(TEST_CREDENTIALS);

		// Submit the form
		await page.getByRole("button", { name: /login/i }).click();

		// Verify redirect to dashboard after successful login
		await expect(page).toHaveURL(/\/dashboard/);
	});
});
