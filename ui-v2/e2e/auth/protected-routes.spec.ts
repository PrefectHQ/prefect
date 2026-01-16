import {
	clearAuthCredentials,
	expect,
	isAuthRequired,
	test,
	waitForServerHealth,
} from "../fixtures";

// Test credentials from environment variable or default
const TEST_CREDENTIALS =
	process.env.PREFECT_E2E_TEST_CREDENTIALS ?? "admin:secret";

// Routes that should be protected when auth is enabled
const PROTECTED_ROUTES = [
	"/dashboard",
	"/runs",
	"/flows",
	"/deployments",
	"/work-pools",
	"/blocks",
	"/variables",
	"/automations",
	"/events",
	"/concurrency-limits",
	"/settings",
];

test.describe("Protected Routes", () => {
	test.beforeAll(async ({ apiClient }) => {
		await waitForServerHealth(apiClient);

		const authRequired = await isAuthRequired();
		test.skip(!authRequired, "Auth is not enabled on the server");
	});

	test.describe("Unauthenticated Access", () => {
		test.beforeEach(async ({ page, context }) => {
			// Clear all storage state to ensure clean auth state
			await context.clearCookies();
			// Navigate to login page first (always accessible) to establish page context
			await page.goto("/login");
			// Clear any existing credentials
			await clearAuthCredentials(page);
			// Also clear all localStorage to be thorough
			await page.evaluate(() => localStorage.clear());
		});

		for (const route of PROTECTED_ROUTES) {
			test(`should redirect ${route} to login when unauthenticated`, async ({
				page,
			}) => {
				await page.goto(route);

				// Should redirect to login
				await expect(page).toHaveURL(/\/login/);
			});
		}
	});

	test.describe("Authenticated Access", () => {
		test.beforeEach(async ({ page }) => {
			// Actually log in through the UI to ensure credentials are validated
			await page.goto("/login");
			await page.getByPlaceholder("admin:pass").fill(TEST_CREDENTIALS);
			await page.getByRole("button", { name: "Login" }).click();
			// Wait for redirect to dashboard (confirms we're authenticated)
			await page.waitForURL(/\/dashboard/);
		});

		for (const route of PROTECTED_ROUTES) {
			test(`should allow access to ${route} when authenticated`, async ({
				page,
			}) => {
				await page.goto(route);

				// Should stay on the route (not redirect to login)
				await expect(page).toHaveURL(new RegExp(route));

				// Should not show login page elements
				await expect(page.getByPlaceholder("admin:pass")).not.toBeVisible();
			});
		}
	});

	test("should preserve redirect parameter through auth flow", async ({
		page,
		context,
	}) => {
		// Clear all storage state to ensure clean auth state
		await context.clearCookies();
		await page.goto("/login");
		await clearAuthCredentials(page);
		await page.evaluate(() => localStorage.clear());

		// Try to access a protected route
		await page.goto("/automations");

		// Should be on login with redirect
		await expect(page).toHaveURL(/\/login/);
		const url = new URL(page.url());
		const redirectParam = url.searchParams.get("redirectTo");
		expect(redirectParam).toContain("/automations");

		// Login
		await page.getByPlaceholder("admin:pass").fill(TEST_CREDENTIALS);
		await page.getByRole("button", { name: "Login" }).click();

		// Should redirect to original page
		await expect(page).toHaveURL(/\/automations/);
	});
});
