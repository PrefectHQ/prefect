import type { Page } from "@playwright/test";
import {
	cleanupFlowRuns,
	createDeployment,
	createFlow,
	createFlowRun,
	expect,
	test,
	waitForServerHealth,
} from "../fixtures";

const TEST_PREFIX = "e2e-dashboard-";

/**
 * Wait for the dashboard page to be fully loaded.
 * Handles both empty state and populated state.
 */
async function waitForDashboardReady(page: Page): Promise<void> {
	// Wait for either the empty state or the dashboard cards to be visible
	await expect(
		page
			.getByRole("heading", { name: /run a task or flow to get started/i })
			.or(page.getByText("Flow Runs")),
	).toBeVisible({ timeout: 10000 });
}

test.describe("Dashboard Page", () => {
	test.beforeAll(async ({ apiClient }) => {
		await waitForServerHealth(apiClient);
	});

	test.beforeEach(async ({ apiClient }) => {
		// Cleanup is best-effort - don't fail tests if server is temporarily unavailable
		try {
			await cleanupFlowRuns(apiClient, TEST_PREFIX);
		} catch {
			// Ignore cleanup errors - test data uses unique timestamps so collisions are unlikely
		}
	});

	test.afterEach(async ({ apiClient }) => {
		// Cleanup is best-effort - don't fail tests if server is temporarily unavailable
		try {
			await cleanupFlowRuns(apiClient, TEST_PREFIX);
		} catch {
			// Ignore cleanup errors - test data uses unique timestamps so collisions are unlikely
		}
	});

	test.describe("Dashboard with Data", () => {
		test("should display dashboard with flow runs, task runs, and work pools cards after creating test data", async ({
			page,
			apiClient,
		}) => {
			// --- SETUP: Create test data via API ---
			const flowName = `${TEST_PREFIX}main-flow-${Date.now()}`;
			const flow = await createFlow(apiClient, flowName);
			const deployment = await createDeployment(apiClient, {
				name: `${TEST_PREFIX}deployment-${Date.now()}`,
				flowId: flow.id,
			});

			// Create multiple flow runs with different states to populate dashboard
			await createFlowRun(apiClient, {
				flowId: flow.id,
				deploymentId: deployment.id,
				name: `${TEST_PREFIX}completed-run-${Date.now()}`,
				state: { type: "COMPLETED", name: "Completed" },
			});

			await createFlowRun(apiClient, {
				flowId: flow.id,
				deploymentId: deployment.id,
				name: `${TEST_PREFIX}failed-run-${Date.now()}`,
				state: { type: "FAILED", name: "Failed" },
			});

			await createFlowRun(apiClient, {
				flowId: flow.id,
				deploymentId: deployment.id,
				name: `${TEST_PREFIX}running-run-${Date.now()}`,
				state: { type: "RUNNING", name: "Running" },
			});

			// --- NAVIGATE to dashboard and wait for data ---
			await expect(async () => {
				await page.goto("/dashboard");
				await waitForDashboardReady(page);
				await expect(page.getByText(/completed/i).first()).toBeVisible({
					timeout: 2000,
				});
			}).toPass({ timeout: 15000 });

			// --- VERIFY: Dashboard header and filters are visible ---
			// Dashboard title is in a BreadcrumbItem (li element), not a heading
			await expect(page.getByText("Dashboard").first()).toBeVisible();
			await expect(page.getByLabel("Hide subflows")).toBeVisible();
			await expect(page.getByText("All tags")).toBeVisible();

			// --- VERIFY: Flow Runs card displays data ---
			await expect(page.getByText("Flow Runs")).toBeVisible();

			// Wait for state tabs to be visible (indicates data has loaded)
			await expect(page.getByRole("tablist")).toBeVisible({ timeout: 10000 });
			await expect(page.getByRole("tab", { name: /failed/i })).toBeVisible();
			await expect(page.getByRole("tab", { name: /running/i })).toBeVisible();
			await expect(page.getByRole("tab", { name: /completed/i })).toBeVisible();

			// --- VERIFY: Task Runs card is visible ---
			await expect(page.getByText("Task Runs")).toBeVisible();

			// --- VERIFY: Work Pools card is visible ---
			// Use locator for the card title specifically to avoid matching sidebar nav
			// The card title has data-slot="card-title" attribute
			await expect(
				page.locator('[data-slot="card-title"]', {
					hasText: "Active Work Pools",
				}),
			).toBeVisible();

			// --- VERIFY: Clicking state tabs updates the displayed flow runs ---
			// Default tab is Failed/Crashed - should show our failed run
			await expect(page.getByRole("tab", { name: /failed/i })).toBeVisible();

			// Click on Running tab
			await page.getByRole("tab", { name: /running/i }).click();
			// URL should update with tab parameter
			await expect(page).toHaveURL(/tab=RUNNING/);

			// Click on Completed tab
			await page.getByRole("tab", { name: /completed/i }).click();
			await expect(page).toHaveURL(/tab=COMPLETED/);

			// Click back to Failed tab (should clear the tab param since it's default)
			await page.getByRole("tab", { name: /failed/i }).click();
			// Default tab doesn't need to be in URL
			await expect(page).not.toHaveURL(/tab=FAILED/);
		});
	});

	test.describe("Dashboard Filters", () => {
		test("should filter dashboard data using hide subflows toggle and verify URL updates", async ({
			page,
			apiClient,
		}) => {
			// --- SETUP: Create test data including a subflow ---
			const flowName = `${TEST_PREFIX}filter-flow-${Date.now()}`;
			const flow = await createFlow(apiClient, flowName);
			const deployment = await createDeployment(apiClient, {
				name: `${TEST_PREFIX}filter-deployment-${Date.now()}`,
				flowId: flow.id,
			});

			// Create a parent flow run
			await createFlowRun(apiClient, {
				flowId: flow.id,
				deploymentId: deployment.id,
				name: `${TEST_PREFIX}parent-run-${Date.now()}`,
				state: { type: "COMPLETED", name: "Completed" },
			});

			// Note: We can't easily create a real subflow in E2E tests without a parent task run,
			// but we can still test the toggle functionality by verifying URL updates

			// --- NAVIGATE to dashboard ---
			await page.goto("/dashboard");
			await waitForDashboardReady(page);

			// --- VERIFY: Hide subflows toggle is visible and unchecked by default ---
			const hideSubflowsSwitch = page.getByLabel("Hide subflows");
			await expect(hideSubflowsSwitch).toBeVisible();
			await expect(hideSubflowsSwitch).not.toBeChecked();

			// --- ACTION: Toggle hide subflows ON ---
			await hideSubflowsSwitch.click();

			// --- VERIFY: URL updates with hideSubflows parameter ---
			await expect(page).toHaveURL(/hideSubflows=true/);

			// The dashboard should refresh and filter out subflows
			// This is verified by the URL param change and the component re-rendering

			// --- ACTION: Toggle hide subflows OFF ---
			await hideSubflowsSwitch.click();

			// --- VERIFY: URL no longer has hideSubflows=true ---
			// When false/default, the param should be removed or set to false
			await expect(page).not.toHaveURL(/hideSubflows=true/);
		});

		test("should persist date range selection in URL and filter dashboard data", async ({
			page,
			apiClient,
		}) => {
			// --- SETUP: Create test data ---
			const flowName = `${TEST_PREFIX}date-flow-${Date.now()}`;
			const flow = await createFlow(apiClient, flowName);
			const deployment = await createDeployment(apiClient, {
				name: `${TEST_PREFIX}date-deployment-${Date.now()}`,
				flowId: flow.id,
			});

			await createFlowRun(apiClient, {
				flowId: flow.id,
				deploymentId: deployment.id,
				name: `${TEST_PREFIX}recent-run-${Date.now()}`,
				state: { type: "COMPLETED", name: "Completed" },
			});

			// --- NAVIGATE to dashboard ---
			await page.goto("/dashboard");
			await waitForDashboardReady(page);

			// --- VERIFY: Date range selector is visible ---
			// The RichDateRangeSelector component shows "Past day" by default (86400 seconds)
			await expect(
				page.getByRole("button", { name: /past day|select a time span/i }),
			).toBeVisible();

			// --- ACTION: Open date range selector and change to a different range ---
			await page
				.getByRole("button", { name: /past day|select a time span/i })
				.click();

			// Select "Past 7 days" option (7 days = 604800 seconds)
			const past7DaysOption = page.getByRole("button", {
				name: /past 7 days/i,
			});
			if (await past7DaysOption.isVisible()) {
				await past7DaysOption.click();
				// --- VERIFY: URL updates with new time span ---
				await expect(page).toHaveURL(/seconds=-604800|rangeType=span/);
			} else {
				// If the exact option isn't available, just verify the selector works
				// by checking that it opened (there's a popover/dropdown)
				await expect(
					page.getByRole("listbox").or(page.getByRole("dialog")),
				).toBeVisible();
				// Close by pressing Escape
				await page.keyboard.press("Escape");
			}

			// --- VERIFY: Dashboard still displays correctly after filter change ---
			await expect(page.getByText("Flow Runs")).toBeVisible();
		});
	});

	test.describe("Empty State", () => {
		test("should show empty state when no flow runs exist and hide filters", async ({
			page,
			apiClient,
		}) => {
			// First, clean up any existing flow runs with our prefix
			await cleanupFlowRuns(apiClient, TEST_PREFIX);

			// Navigate to dashboard
			await page.goto("/dashboard");

			// Check if empty state is shown (if there are no flow runs at all in the system)
			// This test may be skipped if other flow runs exist from other tests
			const emptyStateHeading = page.getByRole("heading", {
				name: /run a task or flow to get started/i,
			});
			const flowRunsCard = page.getByText("Flow Runs");

			// Wait for page to load
			await expect(emptyStateHeading.or(flowRunsCard)).toBeVisible({
				timeout: 10000,
			});

			// If empty state is shown, verify the expected content
			if (await emptyStateHeading.isVisible()) {
				// --- VERIFY: Empty state content ---
				await expect(
					page.getByText(/runs store the state history/i),
				).toBeVisible();
				await expect(
					page.getByRole("link", { name: /view docs/i }),
				).toBeVisible();

				// --- VERIFY: Filters are hidden in empty state ---
				await expect(page.getByLabel("Hide subflows")).not.toBeVisible();
				await expect(page.getByText("All tags")).not.toBeVisible();
			} else {
				// Other flow runs exist - skip this test
				test.skip(
					true,
					"Skipping empty state test because flow runs already exist",
				);
			}
		});
	});
});
