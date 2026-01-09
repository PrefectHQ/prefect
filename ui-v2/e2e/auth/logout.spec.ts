import {
	expect,
	getAuthCredentials,
	isAuthRequired,
	setAuthCredentials,
	test,
	waitForServerHealth,
} from "../fixtures";

// Test credentials from environment variable or default
const TEST_CREDENTIALS =
	process.env.PREFECT_E2E_TEST_CREDENTIALS ?? "admin:secret";

test.describe("Logout Flow", () => {
	test.beforeAll(async ({ apiClient }) => {
		await waitForServerHealth(apiClient);

		const authRequired = await isAuthRequired();
		test.skip(!authRequired, "Auth is not enabled on the server");
	});

	test.beforeEach(async ({ page }) => {
		// Start authenticated
		await page.goto("/login");
		await setAuthCredentials(page, TEST_CREDENTIALS);
	});

	test("should show logout button in sidebar when auth is required", async ({
		page,
	}) => {
		await page.goto("/dashboard");

		// Verify logout button is visible in sidebar
		await expect(page.getByRole("button", { name: /logout/i })).toBeVisible();
	});

	test("should clear credentials and redirect to login on logout", async ({
		page,
	}) => {
		await page.goto("/dashboard");

		// Verify we're authenticated
		const credsBefore = await getAuthCredentials(page);
		expect(credsBefore).toBeTruthy();

		// Click logout button
		await page.getByRole("button", { name: /logout/i }).click();

		// Should redirect to login
		await expect(page).toHaveURL(/\/login/);

		// Credentials should be cleared
		const credsAfter = await getAuthCredentials(page);
		expect(credsAfter).toBeNull();
	});

	test("should prevent access to protected routes after logout", async ({
		page,
	}) => {
		await page.goto("/dashboard");

		// Logout
		await page.getByRole("button", { name: /logout/i }).click();
		await expect(page).toHaveURL(/\/login/);

		// Try to navigate to protected route
		await page.goto("/flows");

		// Should redirect back to login
		await expect(page).toHaveURL(/\/login/);
	});
});
