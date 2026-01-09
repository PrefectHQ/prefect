import {
	expect,
	getAuthCredentials,
	isAuthRequired,
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
		// Start authenticated by actually logging in through the UI
		await page.goto("/login");
		await page.getByPlaceholder("admin:pass").fill(TEST_CREDENTIALS);
		await page.getByRole("button", { name: "Login" }).click();
		// Wait for redirect to dashboard (confirms we're authenticated)
		await page.waitForURL(/\/dashboard/);
	});

	test("should show logout button in sidebar when auth is required", async ({
		page,
	}) => {
		await page.goto("/dashboard");

		// Verify logout button is visible in sidebar (it's a SidebarMenuButton, not a button role)
		await expect(page.getByText("Logout")).toBeVisible();
	});

	test("should clear credentials and redirect to login on logout", async ({
		page,
	}) => {
		await page.goto("/dashboard");

		// Verify we're authenticated
		const credsBefore = await getAuthCredentials(page);
		expect(credsBefore).toBeTruthy();

		// Click logout button (it's a SidebarMenuButton, not a button role)
		await page.getByText("Logout").click();

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

		// Logout (it's a SidebarMenuButton, not a button role)
		await page.getByText("Logout").click();
		await expect(page).toHaveURL(/\/login/);

		// Try to navigate to protected route
		await page.goto("/flows");

		// Should redirect back to login
		await expect(page).toHaveURL(/\/login/);
	});
});
