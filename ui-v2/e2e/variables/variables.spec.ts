import type { Page } from "@playwright/test";
import {
	cleanupVariables,
	createVariable,
	expect,
	listVariables,
	test,
	waitForServerHealth,
} from "../fixtures";

const TEST_PREFIX = "e2e-test-";

/**
 * Wait for the variables page to be fully loaded.
 * This ensures the page has rendered before tests interact with it,
 * which is important when running tests in parallel.
 */
async function waitForVariablesPageReady(page: Page): Promise<void> {
	// Wait for either the empty state heading or the variables table to be visible
	// This handles both cases: when there are no variables and when there are variables
	await expect(
		page
			.getByRole("heading", { name: /add a variable to get started/i })
			.or(page.getByRole("table")),
	).toBeVisible();
}

test.describe("Variables Page", () => {
	test.beforeAll(async ({ apiClient }) => {
		await waitForServerHealth(apiClient);
	});

	test.beforeEach(async ({ apiClient }) => {
		await cleanupVariables(apiClient, TEST_PREFIX);
	});

	test.afterEach(async ({ apiClient }) => {
		await cleanupVariables(apiClient, TEST_PREFIX);
	});

	test.describe("Empty State", () => {
		test("should show empty state when no variables exist", async ({
			page,
		}) => {
			await page.goto("/variables");

			await expect(
				page.getByRole("heading", { name: /add a variable to get started/i }),
			).toBeVisible();
			await expect(
				page.getByRole("button", { name: /add variable/i }),
			).toBeVisible();
			await expect(
				page.getByRole("link", { name: /view docs/i }),
			).toBeVisible();
		});
	});

	test.describe("Create Variable", () => {
		test("should create a variable with string value via dialog", async ({
			page,
			apiClient,
		}) => {
			const variableName = `${TEST_PREFIX}string-var-${Date.now()}`;
			const variableValue = "test-string-value";

			await page.goto("/variables");
			await waitForVariablesPageReady(page);

			// Click Add Variable button
			await page.getByRole("button", { name: /add variable/i }).click();

			// Verify dialog opens
			await expect(
				page.getByRole("dialog", { name: /new variable/i }),
			).toBeVisible();

			// Fill in the form
			await page.getByRole("textbox", { name: /name/i }).fill(variableName);

			// Fill JSON value - the input expects valid JSON so we need to quote the string
			const jsonInput = page.locator(".cm-content");
			await jsonInput.click();
			await page.keyboard.type(`"${variableValue}"`);

			// Click Create
			await page.getByRole("button", { name: /create/i }).click();

			// Wait for dialog to close and variable to appear in list
			await expect(page.getByRole("dialog")).not.toBeVisible();
			await expect(page.getByText(variableName)).toBeVisible();

			// Verify via API
			const variables = await listVariables(apiClient);
			const created = variables.find((v) => v.name === variableName);
			expect(created).toBeDefined();
			expect(created?.value).toBe(variableValue);
		});

		test("should create a variable with JSON object value", async ({
			page,
			apiClient,
		}) => {
			const variableName = `${TEST_PREFIX}json-var-${Date.now()}`;
			const variableValue = { key: "value", number: 42 };

			await page.goto("/variables");
			await waitForVariablesPageReady(page);

			await page.getByRole("button", { name: /add variable/i }).click();
			await expect(
				page.getByRole("dialog", { name: /new variable/i }),
			).toBeVisible();

			await page.getByRole("textbox", { name: /name/i }).fill(variableName);

			const jsonInput = page.locator(".cm-content");
			await jsonInput.click();
			await page.keyboard.type(JSON.stringify(variableValue));

			await page.getByRole("button", { name: /create/i }).click();

			await expect(page.getByRole("dialog")).not.toBeVisible();
			await expect(page.getByText(variableName)).toBeVisible();

			// Verify via API with polling to handle eventual consistency
			await expect
				.poll(
					async () => {
						const variables = await listVariables(apiClient);
						return variables.find((v) => v.name === variableName);
					},
					{ timeout: 10000 },
				)
				.toBeDefined();

			const variables = await listVariables(apiClient);
			const created = variables.find((v) => v.name === variableName);
			expect(created?.value).toEqual(variableValue);
		});

		test("should create a variable with tags", async ({ page, apiClient }) => {
			const variableName = `${TEST_PREFIX}tagged-var-${Date.now()}`;
			const tags = ["production", "config"];

			await page.goto("/variables");
			await waitForVariablesPageReady(page);

			await page.getByRole("button", { name: /add variable/i }).click();
			await expect(
				page.getByRole("dialog", { name: /new variable/i }),
			).toBeVisible();

			await page.getByRole("textbox", { name: /name/i }).fill(variableName);

			const jsonInput = page.locator(".cm-content");
			await jsonInput.click();
			await page.keyboard.type('"tagged-value"');

			// Add tags - use dialog-scoped selector to avoid matching filter input
			const dialog = page.getByRole("dialog");
			const tagsInput = dialog.getByRole("textbox", { name: /tags/i });
			for (const tag of tags) {
				await tagsInput.fill(tag);
				await page.keyboard.press("Enter");
			}

			await page.getByRole("button", { name: /create/i }).click();

			await expect(page.getByRole("dialog")).not.toBeVisible();
			await expect(page.getByText(variableName)).toBeVisible();

			// Verify via API
			const variables = await listVariables(apiClient);
			const created = variables.find((v) => v.name === variableName);
			expect(created).toBeDefined();
			expect(created?.tags).toEqual(expect.arrayContaining(tags));
		});

		test("should close dialog when clicking Close button", async ({ page }) => {
			await page.goto("/variables");
			await waitForVariablesPageReady(page);

			await page.getByRole("button", { name: /add variable/i }).click();

			const dialog = page.getByRole("dialog", { name: /new variable/i });
			await expect(dialog).toBeVisible();

			// Click the Close button in the dialog footer (not the X button in the corner)
			// Wait for the button to be visible and enabled before clicking
			const closeButton = dialog
				.locator("form")
				.getByRole("button", { name: /close/i });
			await expect(closeButton).toBeVisible();
			await expect(closeButton).toBeEnabled();

			// Wait for dialog animation to complete (200ms duration) before clicking
			// This ensures the DialogClose event handler is fully attached
			await page.waitForTimeout(250);

			await closeButton.click();

			await expect(dialog).not.toBeVisible();
		});
	});

	test.describe("Edit Variable", () => {
		test("should edit an existing variable", async ({ page, apiClient }) => {
			// Create a variable via API first
			const variableName = `${TEST_PREFIX}edit-var-${Date.now()}`;
			const initialValue = "initial-value";
			const updatedValue = "updated-value";

			await createVariable(apiClient, {
				name: variableName,
				value: initialValue,
			});

			// Use toPass to handle eventual consistency - retry navigation if data not visible
			await expect(async () => {
				await page.goto("/variables");
				await expect(page.getByText(variableName)).toBeVisible({
					timeout: 2000,
				});
			}).toPass({ timeout: 15000 });

			// Find the row containing our variable and click its actions menu
			const variableRow = page
				.getByRole("row")
				.filter({ hasText: variableName });
			await variableRow.getByRole("button", { name: /open menu/i }).click();
			await page.getByRole("menuitem", { name: /edit/i }).click();

			// Verify edit dialog opens with correct title
			await expect(
				page.getByRole("dialog", { name: /edit variable/i }),
			).toBeVisible();

			// Verify name is pre-filled
			await expect(page.getByRole("textbox", { name: /name/i })).toHaveValue(
				variableName,
			);

			// Update the value
			const jsonInput = page.locator(".cm-content");
			await jsonInput.click();
			await page.keyboard.press("Control+A");
			await page.keyboard.type(`"${updatedValue}"`);

			// Save
			await page.getByRole("button", { name: /save/i }).click();

			// Wait for dialog to close
			await expect(page.getByRole("dialog")).not.toBeVisible();

			// Verify via API
			const variables = await listVariables(apiClient);
			const updated = variables.find((v) => v.name === variableName);
			expect(updated?.value).toBe(updatedValue);
		});
	});

	test.describe("Delete Variable", () => {
		test("should delete a variable via actions menu", async ({
			page,
			apiClient,
		}) => {
			// Create a variable via API first
			const variableName = `${TEST_PREFIX}delete-var-${Date.now()}`;

			await createVariable(apiClient, {
				name: variableName,
				value: "to-be-deleted",
			});

			// Use toPass to handle eventual consistency - retry navigation if data not visible
			await expect(async () => {
				await page.goto("/variables");
				await expect(page.getByText(variableName)).toBeVisible({
					timeout: 2000,
				});
			}).toPass({ timeout: 15000 });

			// Find the row containing our variable and click its actions menu
			const variableRow = page
				.getByRole("row")
				.filter({ hasText: variableName });
			await variableRow.getByRole("button", { name: /open menu/i }).click();
			await page.getByRole("menuitem", { name: /delete/i }).click();

			// Wait for variable to be removed from list
			await expect(page.getByText(variableName)).not.toBeVisible();

			// Verify via API
			const variables = await listVariables(apiClient);
			const deleted = variables.find((v) => v.name === variableName);
			expect(deleted).toBeUndefined();
		});
	});

	test.describe("Search and Filter", () => {
		// Use unique suffix per test run to avoid conflicts with parallel test execution
		let filterTestSuffix: string;
		let alphaVarName: string;
		let betaVarName: string;
		let gammaVarName: string;

		test.beforeEach(async ({ apiClient }) => {
			// Generate unique suffix for this test run
			filterTestSuffix = `${Date.now()}`;
			alphaVarName = `${TEST_PREFIX}alpha-${filterTestSuffix}`;
			betaVarName = `${TEST_PREFIX}beta-${filterTestSuffix}`;
			gammaVarName = `${TEST_PREFIX}gamma-${filterTestSuffix}`;

			// Create multiple test variables for filtering tests
			await createVariable(apiClient, {
				name: alphaVarName,
				value: "alpha",
				tags: ["production"],
			});
			await createVariable(apiClient, {
				name: betaVarName,
				value: "beta",
				tags: ["staging"],
			});
			await createVariable(apiClient, {
				name: gammaVarName,
				value: "gamma",
				tags: ["production", "config"],
			});
		});

		test("should filter variables by name search", async ({ page }) => {
			await page.goto("/variables");

			// Wait for variables to load
			await expect(page.getByText(alphaVarName)).toBeVisible();
			await expect(page.getByText(betaVarName)).toBeVisible();
			await expect(page.getByText(gammaVarName)).toBeVisible();

			// Search for "alpha"
			await page.getByPlaceholder("Search variables").fill("alpha");

			// Should only show alpha variable
			await expect(page.getByText(alphaVarName)).toBeVisible();
			await expect(page.getByText(betaVarName)).not.toBeVisible();
			await expect(page.getByText(gammaVarName)).not.toBeVisible();

			// Verify URL updated with search param
			await expect(page).toHaveURL(/name=alpha/);
		});

		test("should filter variables by tag", async ({ page }) => {
			await page.goto("/variables");

			// Wait for variables to load
			await expect(page.getByText(alphaVarName)).toBeVisible();

			// Filter by "production" tag
			const tagsFilter = page.getByPlaceholder("Filter by tags");
			await tagsFilter.fill("production");
			await page.keyboard.press("Enter");

			// Should show alpha and gamma (both have production tag)
			await expect(page.getByText(alphaVarName)).toBeVisible();
			await expect(page.getByText(gammaVarName)).toBeVisible();
			await expect(page.getByText(betaVarName)).not.toBeVisible();

			// Verify URL updated with tags param (tags are URL-encoded as an array)
			await expect(page).toHaveURL(/tags=/);
		});

		test("should combine name search and tag filter", async ({ page }) => {
			await page.goto("/variables");

			// Wait for variables to load
			await expect(page.getByText(alphaVarName)).toBeVisible();

			// Filter by "production" tag first
			const tagsFilter = page.getByPlaceholder("Filter by tags");
			await tagsFilter.fill("production");
			await page.keyboard.press("Enter");

			// Then search for "gamma"
			await page.getByPlaceholder("Search variables").fill("gamma");

			// Should only show gamma (has production tag AND matches gamma search)
			await expect(page.getByText(gammaVarName)).toBeVisible();
			await expect(page.getByText(alphaVarName)).not.toBeVisible();
			await expect(page.getByText(betaVarName)).not.toBeVisible();
		});
	});

	test.describe("Sorting", () => {
		// Use unique suffix per test run to avoid conflicts with parallel test execution
		let sortTestSuffix: string;
		let aaaVarName: string;
		let zzzVarName: string;

		test.beforeEach(async ({ apiClient }) => {
			// Generate unique suffix for this test run
			sortTestSuffix = `${Date.now()}`;
			aaaVarName = `${TEST_PREFIX}aaa-sort-${sortTestSuffix}`;
			zzzVarName = `${TEST_PREFIX}zzz-sort-${sortTestSuffix}`;

			// Create variables with specific names for sorting tests
			await createVariable(apiClient, {
				name: aaaVarName,
				value: "first",
			});
			// Small delay to ensure different timestamps
			await new Promise((resolve) => setTimeout(resolve, 100));
			await createVariable(apiClient, {
				name: zzzVarName,
				value: "last",
			});
		});

		test("should sort variables by name A to Z", async ({ page }) => {
			// Use toPass to handle eventual consistency - retry navigation if data not visible
			await expect(async () => {
				await page.goto("/variables");
				await expect(page.getByText(aaaVarName)).toBeVisible({ timeout: 2000 });
			}).toPass({ timeout: 15000 });

			// Change sort to A to Z
			await page
				.getByRole("combobox", { name: /variable sort order/i })
				.click();
			await page.getByRole("option", { name: "A to Z" }).click();

			// Verify URL updated
			await expect(page).toHaveURL(/sort=NAME_ASC/);

			// Get all variable names in order
			const firstRow = page.getByRole("row").nth(1); // nth(1) skips header row
			await expect(firstRow).toContainText(aaaVarName);
		});

		test("should sort variables by name Z to A", async ({ page }) => {
			// Use toPass to handle eventual consistency - retry navigation if data not visible
			await expect(async () => {
				await page.goto("/variables");
				await expect(page.getByText(aaaVarName)).toBeVisible({ timeout: 2000 });
			}).toPass({ timeout: 15000 });

			// Change sort to Z to A
			await page
				.getByRole("combobox", { name: /variable sort order/i })
				.click();
			await page.getByRole("option", { name: "Z to A" }).click();

			// Verify URL updated
			await expect(page).toHaveURL(/sort=NAME_DESC/);

			// Verify zzz comes before aaa
			const firstRow = page.getByRole("row").nth(1); // nth(1) skips header row
			await expect(firstRow).toContainText(zzzVarName);
		});

		test("should sort variables by created date (default)", async ({
			page,
		}) => {
			// Use toPass to handle eventual consistency - retry navigation if data not visible
			await expect(async () => {
				await page.goto("/variables");
				await expect(page.getByText(zzzVarName)).toBeVisible({ timeout: 2000 });
			}).toPass({ timeout: 15000 });

			// Verify default sort is CREATED_DESC
			await expect(page).toHaveURL(/sort=CREATED_DESC/);

			// Most recently created should be first
			const firstRow = page.getByRole("row").nth(1); // nth(1) skips header row
			await expect(firstRow).toContainText(zzzVarName);
		});
	});

	test.describe("Pagination", () => {
		// Use unique suffix per test run to avoid conflicts with parallel test execution
		let paginationTestSuffix: string;

		test.beforeEach(async ({ apiClient }) => {
			// Generate unique suffix for this test run
			paginationTestSuffix = `${Date.now()}`;

			// Create enough variables to test pagination (more than default page size of 10)
			const createPromises = [];
			for (let i = 0; i < 15; i++) {
				createPromises.push(
					createVariable(apiClient, {
						name: `${TEST_PREFIX}page-${paginationTestSuffix}-${String(i).padStart(2, "0")}`,
						value: `value-${i}`,
					}),
				);
			}
			await Promise.all(createPromises);
		});

		test("should show correct page count", async ({ page }) => {
			// Use toPass to handle eventual consistency with parallel test execution
			await expect(async () => {
				await page.goto("/variables");
				await expect(page.getByText("Page 1 of 2")).toBeVisible({
					timeout: 2000,
				});
			}).toPass({ timeout: 15000 });
		});

		test("should navigate to next page", async ({ page }) => {
			// Use toPass to handle eventual consistency with parallel test execution
			await expect(async () => {
				await page.goto("/variables");
				await expect(page.getByText("Page 1 of 2")).toBeVisible({
					timeout: 2000,
				});
			}).toPass({ timeout: 15000 });

			// Click next page
			await page.getByRole("button", { name: "Go to next page" }).click();

			// Verify page changed
			await expect(page.getByText("Page 2 of 2")).toBeVisible();
			await expect(page).toHaveURL(/offset=10/);
		});

		test("should navigate to previous page", async ({ page }) => {
			// Use toPass to handle eventual consistency with parallel test execution
			await expect(async () => {
				await page.goto("/variables?offset=10&limit=10&sort=CREATED_DESC");
				await expect(page.getByText("Page 2 of 2")).toBeVisible({
					timeout: 2000,
				});
			}).toPass({ timeout: 15000 });

			// Click previous page
			await page.getByRole("button", { name: "Go to previous page" }).click();

			// Verify page changed
			await expect(page.getByText("Page 1 of 2")).toBeVisible();
			await expect(page).toHaveURL(/offset=0/);
		});

		test("should change items per page", async ({ page }) => {
			// Use toPass to handle eventual consistency with parallel test execution
			await expect(async () => {
				await page.goto("/variables");
				await expect(page.getByText("Page 1 of 2")).toBeVisible({
					timeout: 2000,
				});
			}).toPass({ timeout: 15000 });

			// Change to 25 items per page
			await page.getByRole("combobox", { name: "Items per page" }).click();
			await page.getByRole("option", { name: "25" }).click();

			// With 15 items and 25 per page, should be 1 page
			await expect(page.getByText("Page 1 of 1")).toBeVisible();
			await expect(page).toHaveURL(/limit=25/);
		});

		test("should disable previous buttons on first page", async ({ page }) => {
			// Use toPass to handle eventual consistency with parallel test execution
			await expect(async () => {
				await page.goto("/variables");
				await expect(page.getByText("Page 1 of 2")).toBeVisible({
					timeout: 2000,
				});
			}).toPass({ timeout: 15000 });

			// On first page, previous buttons should be disabled
			await expect(
				page.getByRole("button", { name: "Go to first page" }),
			).toBeDisabled();
			await expect(
				page.getByRole("button", { name: "Go to previous page" }),
			).toBeDisabled();

			// Next buttons should be enabled
			await expect(
				page.getByRole("button", { name: "Go to next page" }),
			).toBeEnabled();
			await expect(
				page.getByRole("button", { name: "Go to last page" }),
			).toBeEnabled();
		});

		test("should disable next buttons on last page", async ({ page }) => {
			// Use toPass to handle eventual consistency with parallel test execution
			await expect(async () => {
				await page.goto("/variables?offset=10&limit=10&sort=CREATED_DESC");
				await expect(page.getByText("Page 2 of 2")).toBeVisible({
					timeout: 2000,
				});
			}).toPass({ timeout: 15000 });

			// On last page, next buttons should be disabled
			await expect(
				page.getByRole("button", { name: "Go to next page" }),
			).toBeDisabled();
			await expect(
				page.getByRole("button", { name: "Go to last page" }),
			).toBeDisabled();

			// Previous buttons should be enabled
			await expect(
				page.getByRole("button", { name: "Go to first page" }),
			).toBeEnabled();
			await expect(
				page.getByRole("button", { name: "Go to previous page" }),
			).toBeEnabled();
		});
	});
});
