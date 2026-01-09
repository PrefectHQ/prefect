import {
	clearAuthCredentials,
	expect,
	getAuthCredentials,
	isAuthRequired,
	setAuthCredentials,
	test,
	waitForServerHealth,
} from "../fixtures";

// These tests require the server to be started with auth enabled.
// Set PREFECT_E2E_TEST_CREDENTIALS env var to match your server's auth string.
// Default format is "username:password" (e.g., "admin:secret")
const TEST_CREDENTIALS =
	process.env.PREFECT_E2E_TEST_CREDENTIALS ?? "admin:secret";
const INVALID_CREDENTIALS = "invalid:credentials";

test.describe("Login Flow", () => {
	test.beforeAll(async ({ apiClient }) => {
		await waitForServerHealth(apiClient);

		// Skip tests if auth is not enabled
		const authRequired = await isAuthRequired();
		test.skip(!authRequired, "Auth is not enabled on the server");
	});

	test.beforeEach(async ({ page }) => {
		// Navigate to login page first (always accessible) to establish page context
		await page.goto("/login");
		// Clear any existing credentials and reload to reset app auth state
		await clearAuthCredentials(page);
		await page.reload();
	});

	test("should redirect unauthenticated user to login page", async ({
		page,
	}) => {
		await page.goto("/dashboard");

		// Should be redirected to login with redirect parameter
		await expect(page).toHaveURL(/\/login/);
		await expect(page.getByRole("heading", { name: "Login" })).toBeVisible();
	});

	test("should display login form elements", async ({ page }) => {
		await page.goto("/login");

		// Verify login form is displayed
		await expect(page.getByRole("heading", { name: "Login" })).toBeVisible();
		await expect(page.getByPlaceholder("admin:pass")).toBeVisible();
		await expect(page.getByRole("button", { name: "Login" })).toBeVisible();
	});

	test("should show error for invalid credentials", async ({ page }) => {
		await page.goto("/login");

		// Enter invalid credentials
		await page.getByPlaceholder("admin:pass").fill(INVALID_CREDENTIALS);
		await page.getByRole("button", { name: "Login" }).click();

		// Wait for error message
		await expect(page.getByText(/invalid credentials/i)).toBeVisible();

		// Should still be on login page
		await expect(page).toHaveURL(/\/login/);
	});

	test("should login successfully with valid credentials", async ({ page }) => {
		await page.goto("/login");

		// Enter valid credentials
		await page.getByPlaceholder("admin:pass").fill(TEST_CREDENTIALS);
		await page.getByRole("button", { name: "Login" }).click();

		// Should redirect to dashboard (default redirect)
		await expect(page).toHaveURL(/\/dashboard/);

		// Verify credentials are stored
		const stored = await getAuthCredentials(page);
		expect(stored).toBeTruthy();
	});

	test("should redirect to original page after login", async ({ page }) => {
		// Try to access flows page without auth
		await page.goto("/flows");

		// Should redirect to login with redirect parameter
		await expect(page).toHaveURL(/\/login.*redirect/);

		// Login with valid credentials
		await page.getByPlaceholder("admin:pass").fill(TEST_CREDENTIALS);
		await page.getByRole("button", { name: "Login" }).click();

		// Should redirect back to flows page
		await expect(page).toHaveURL(/\/flows/);
	});

	test("should prevent submission with empty password", async ({ page }) => {
		await page.goto("/login");

		// Try to submit with empty password
		await page.getByRole("button", { name: "Login" }).click();

		// Should still be on login page (form prevents empty submission)
		await expect(page).toHaveURL(/\/login/);
	});

	test("should redirect authenticated user away from login page", async ({
		page,
	}) => {
		// First, authenticate
		await page.goto("/login");
		await setAuthCredentials(page, TEST_CREDENTIALS);

		// Reload to pick up credentials
		await page.reload();

		// Try to visit login page when already authenticated
		await page.goto("/login");

		// Should redirect to dashboard
		await expect(page).toHaveURL(/\/dashboard/);
	});
});
