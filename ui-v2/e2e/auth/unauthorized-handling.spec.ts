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
const AUTH_STORAGE_KEY = "prefect-password";

test.describe("401 Unauthorized Handling", () => {
	test.beforeAll(async ({ apiClient }) => {
		await waitForServerHealth(apiClient);

		const authRequired = await isAuthRequired();
		test.skip(!authRequired, "Auth is not enabled on the server");
	});

	test("should redirect to login when credentials are manually cleared", async ({
		page,
	}) => {
		// Login first
		await page.goto("/login");
		await page.getByPlaceholder("admin:pass").fill(TEST_CREDENTIALS);
		await page.getByRole("button", { name: "Login" }).click();

		// Should be on dashboard
		await expect(page).toHaveURL(/\/dashboard/);

		// Manually clear credentials (simulating expiry or tampering)
		await page.evaluate((key) => {
			localStorage.removeItem(key);
		}, AUTH_STORAGE_KEY);

		// Navigate to trigger auth check
		await page.goto("/flows");

		// Should redirect to login due to missing credentials
		await expect(page).toHaveURL(/\/login/);
	});

	test("should clear invalid credentials and redirect on 401", async ({
		page,
	}) => {
		// Login with valid credentials first
		await page.goto("/login");
		await page.getByPlaceholder("admin:pass").fill(TEST_CREDENTIALS);
		await page.getByRole("button", { name: "Login" }).click();
		await expect(page).toHaveURL(/\/dashboard/);

		// Corrupt the stored credentials
		await page.evaluate((key) => {
			localStorage.setItem(key, "invalid-base64-garbage");
		}, AUTH_STORAGE_KEY);

		// Reload to trigger API calls with invalid credentials
		await page.reload();

		// The 401 handler should clear credentials and redirect
		// Note: This depends on when the first API call happens
		// We may need to wait for the auth:unauthorized event to propagate
		await page.waitForURL(/\/login/, { timeout: 5000 }).catch(() => {
			// If we're still on dashboard, the API call hasn't happened yet
			// Navigate to trigger it
			page.goto("/flows");
		});

		await expect(page).toHaveURL(/\/login/);

		// Credentials should be cleared
		const creds = await getAuthCredentials(page);
		expect(creds).toBeNull();
	});

	test("should handle session becoming invalid gracefully", async ({
		page,
	}) => {
		// This test simulates the scenario where credentials were valid
		// but the server's auth string changed (or session expired in other systems)

		// Login
		await page.goto("/login");
		await page.getByPlaceholder("admin:pass").fill(TEST_CREDENTIALS);
		await page.getByRole("button", { name: "Login" }).click();
		await expect(page).toHaveURL(/\/dashboard/);

		// Store a different (now invalid) credential
		// This simulates the server changing its auth string
		await page.evaluate(
			([key, value]) => {
				localStorage.setItem(key, value);
			},
			[AUTH_STORAGE_KEY, Buffer.from("wrong:creds").toString("base64")] as [
				string,
				string,
			],
		);

		// Try to interact with the app - this should trigger a 401
		// We'll navigate to a page that makes API calls
		await page.goto("/flows");

		// Should eventually redirect to login
		// The timing depends on when the 401 is received and processed
		await expect(page).toHaveURL(/\/login/, { timeout: 10000 });
	});
});
