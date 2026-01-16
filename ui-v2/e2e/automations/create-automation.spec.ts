import {
	cleanupAutomations,
	expect,
	listAutomations,
	test,
	waitForServerHealth,
} from "../fixtures";

const TEST_PREFIX = "e2e-test-";

test.describe("Create Automation", () => {
	test.beforeAll(async ({ apiClient }) => {
		await waitForServerHealth(apiClient);
	});

	test.beforeEach(async ({ apiClient }) => {
		await cleanupAutomations(apiClient, TEST_PREFIX);
	});

	test.afterEach(async ({ apiClient }) => {
		await cleanupAutomations(apiClient, TEST_PREFIX);
	});

	test("should create a flow-run-state automation via the wizard", async ({
		page,
		apiClient,
	}) => {
		const automationName = `${TEST_PREFIX}flow-run-state-automation-${Date.now()}`;
		const automationDescription = "E2E test automation for flow run state";

		// Navigate to automation creation page
		await page.goto("/automations/create");

		// Verify we're on the Trigger step
		await expect(page.getByRole("button", { name: /trigger/i })).toBeVisible();

		// Select flow-run-state trigger template from combobox
		await page.getByLabel("Trigger Template").click();
		await page.getByRole("option", { name: "Flow run state" }).click();

		// Click Next to go to Actions step
		await page.getByRole("button", { name: /next/i }).click();

		// Verify we're on Actions step - wait for action select to be visible
		await expect(page.getByLabel(/select action/i)).toBeVisible();

		// Select cancel-flow-run action type
		await page.getByLabel(/select action/i).click();
		await page.getByRole("option", { name: "Cancel a flow run" }).click();

		// Click Next to go to Details step
		await page.getByRole("button", { name: /next/i }).click();

		// Verify we're on Details step
		await expect(page.getByLabel(/automation name/i)).toBeVisible();

		// Fill automation name and description
		await page.getByLabel(/automation name/i).fill(automationName);
		await page.getByLabel(/description/i).fill(automationDescription);

		// Click Save
		await page.getByRole("button", { name: /save/i }).click();

		// Verify navigation to /automations
		await expect(page).toHaveURL(/\/automations$/);

		// Verify automation appears in list
		await expect(page.getByText(automationName)).toBeVisible();

		// Verify via API client that automation was created
		const automations = await listAutomations(apiClient);
		const createdAutomation = automations.find(
			(a) => a.name === automationName,
		);
		expect(createdAutomation).toBeDefined();
		expect(createdAutomation?.description).toBe(automationDescription);
		expect(createdAutomation?.enabled).toBe(true);
	});

	test("should show validation error when name is missing", async ({
		page,
	}) => {
		// Navigate to automation creation page
		await page.goto("/automations/create");

		// Select a trigger template to enable navigation
		await page.getByLabel("Trigger Template").click();
		await page.getByRole("option", { name: "Flow run state" }).click();

		// Click Next to go to Actions step
		await page.getByRole("button", { name: /next/i }).click();

		// Wait for Actions step
		await expect(page.getByLabel(/select action/i)).toBeVisible();

		// Select an action
		await page.getByLabel(/select action/i).click();
		await page.getByRole("option", { name: "Cancel a flow run" }).click();

		// Click Next to go to Details step
		await page.getByRole("button", { name: /next/i }).click();

		// Verify we're on Details step
		await expect(page.getByLabel(/automation name/i)).toBeVisible();

		// Try to save without filling in name
		await page.getByRole("button", { name: /save/i }).click();

		// Verify validation error appears
		await expect(page.getByText(/required/i)).toBeVisible();

		// Verify still on create page
		await expect(page).toHaveURL(/\/automations\/create/);
	});

	test("should allow canceling automation creation", async ({ page }) => {
		// Navigate to automation creation page
		await page.goto("/automations/create");

		// Verify we're on the create page
		await expect(page.getByLabel("Trigger Template")).toBeVisible();

		// Click cancel link
		await page.getByRole("link", { name: /cancel/i }).click();

		// Verify navigation to /automations
		await expect(page).toHaveURL(/\/automations$/);
	});
});
