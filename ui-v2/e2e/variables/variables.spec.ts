import type { Page } from "@playwright/test";
import {
	cleanupVariables,
	createVariable,
	expect,
	listVariables,
	test,
	waitForServerHealth,
} from "../fixtures";

const CREATE_PREFIX = "e2e-create-";
const EDIT_PREFIX = "e2e-edit-";
const DELETE_PREFIX = "e2e-delete-";
const FILTER_PREFIX = "e2e-filter-";

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

	test.describe("Empty State", () => {
		test("should show empty state when no variables exist", async ({
			page,
			apiClient,
		}) => {
			const variables = await listVariables(apiClient);
			test.skip(
				variables.length > 0,
				"Skipping empty state test because variables already exist",
			);

			await page.goto("/variables");

			await expect(
				page.getByRole("heading", { name: /add a variable to get started/i }),
			).toBeVisible();
			await expect(
				page.getByRole("button", { name: "Add Variable", exact: true }),
			).toBeVisible();
			await expect(
				page.getByRole("link", { name: /view docs/i }),
			).toBeVisible();
		});
	});

	test.describe("Create Variable", () => {
		test.beforeEach(async ({ apiClient }) => {
			await cleanupVariables(apiClient, CREATE_PREFIX);
		});

		test.afterEach(async ({ apiClient }) => {
			await cleanupVariables(apiClient, CREATE_PREFIX);
		});

		test("should create a variable with string value via dialog", async ({
			page,
			apiClient,
		}) => {
			const variableName = `${CREATE_PREFIX}string-${Date.now()}`;
			const variableValue = "test-string-value";

			await page.goto("/variables");
			await waitForVariablesPageReady(page);

			// Click Add Variable button
			await page
				.getByRole("button", { name: /add variable/i })
				.first()
				.click();

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
			await expect
				.poll(
					async () => {
						const variables = await listVariables(apiClient);
						const found = variables.find((v) => v.name === variableName);
						return found?.value;
					},
					{ timeout: 10_000 },
				)
				.toBe(variableValue);
		});

		test("should create a variable with JSON object value", async ({
			page,
			apiClient,
		}) => {
			const variableName = `${CREATE_PREFIX}json-${Date.now()}`;
			const variableValue = { key: "value", number: 42 };

			await page.goto("/variables");
			await waitForVariablesPageReady(page);

			await page
				.getByRole("button", { name: /add variable/i })
				.first()
				.click();
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
			const variableName = `${CREATE_PREFIX}tagged-${Date.now()}`;
			const tags = ["production", "config"];

			await page.goto("/variables");
			await waitForVariablesPageReady(page);

			await page
				.getByRole("button", { name: /add variable/i })
				.first()
				.click();
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
			await expect
				.poll(
					async () => {
						const variables = await listVariables(apiClient);
						return variables.find((v) => v.name === variableName);
					},
					{ timeout: 10_000 },
				)
				.toEqual(
					expect.objectContaining({
						tags: expect.arrayContaining(tags),
					}),
				);
		});

		test("should close dialog when clicking Close button", async ({ page }) => {
			await expect(async () => {
				await page.goto("/variables");
				await waitForVariablesPageReady(page);
				await page
					.getByRole("button", { name: /add variable/i })
					.first()
					.click({ timeout: 2000 });
			}).toPass({ timeout: 15000 });

			const dialog = page.getByRole("dialog", { name: /new variable/i });
			await expect(dialog).toBeVisible();

			const closeButton = dialog
				.locator("form")
				.getByRole("button", { name: /close/i });
			await expect(closeButton).toBeVisible();
			await expect(closeButton).toBeEnabled();

			await expect(async () => {
				await closeButton.click({ timeout: 2000 });
				await expect(dialog).not.toBeVisible({ timeout: 2000 });
			}).toPass({ timeout: 15000 });
		});
	});

	test.describe("Edit Variable", () => {
		test.beforeEach(async ({ apiClient }) => {
			await cleanupVariables(apiClient, EDIT_PREFIX);
		});

		test.afterEach(async ({ apiClient }) => {
			await cleanupVariables(apiClient, EDIT_PREFIX);
		});

		test("should edit an existing variable", async ({ page, apiClient }) => {
			const variableName = `${EDIT_PREFIX}${Date.now()}`;
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
			await expect
				.poll(
					async () => {
						const variables = await listVariables(apiClient);
						const found = variables.find((v) => v.name === variableName);
						return found?.value;
					},
					{ timeout: 10_000 },
				)
				.toBe(updatedValue);
		});
	});

	test.describe("Delete Variable", () => {
		test.beforeEach(async ({ apiClient }) => {
			await cleanupVariables(apiClient, DELETE_PREFIX);
		});

		test.afterEach(async ({ apiClient }) => {
			await cleanupVariables(apiClient, DELETE_PREFIX);
		});

		test("should delete a variable via actions menu", async ({
			page,
			apiClient,
		}) => {
			const variableName = `${DELETE_PREFIX}${Date.now()}`;

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
		let filterTestSuffix: string;
		let alphaVarName: string;
		let betaVarName: string;
		let gammaVarName: string;

		test.beforeEach(async ({ apiClient }) => {
			await cleanupVariables(apiClient, FILTER_PREFIX);
			filterTestSuffix = `${Date.now()}`;
			alphaVarName = `${FILTER_PREFIX}alpha-${filterTestSuffix}`;
			betaVarName = `${FILTER_PREFIX}beta-${filterTestSuffix}`;
			gammaVarName = `${FILTER_PREFIX}gamma-${filterTestSuffix}`;

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

		test.afterEach(async ({ apiClient }) => {
			await cleanupVariables(apiClient, FILTER_PREFIX);
		});

		test("should filter variables by name search", async ({ page }) => {
			// Use toPass retry pattern to handle slow page loads under CI load
			await expect(async () => {
				await page.goto("/variables");
				await expect(page.getByText(alphaVarName)).toBeVisible({
					timeout: 2000,
				});
				await expect(page.getByText(betaVarName)).toBeVisible({
					timeout: 2000,
				});
				await expect(page.getByText(gammaVarName)).toBeVisible({
					timeout: 2000,
				});
			}).toPass({ timeout: 15000 });

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
			// Use toPass retry pattern to handle slow page loads under CI load
			await expect(async () => {
				await page.goto("/variables");
				await expect(page.getByText(alphaVarName)).toBeVisible({
					timeout: 2000,
				});
			}).toPass({ timeout: 15000 });

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
			// Use toPass retry pattern to handle slow page loads under CI load
			await expect(async () => {
				await page.goto("/variables");
				await expect(page.getByText(alphaVarName)).toBeVisible({
					timeout: 2000,
				});
			}).toPass({ timeout: 15000 });

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
		const SORT_PREFIX = "e2e-sort-";
		let sortTestSuffix: string;
		let aaaVarName: string;
		let zzzVarName: string;

		test.beforeEach(async ({ apiClient }) => {
			sortTestSuffix = `${Date.now()}`;
			aaaVarName = `${SORT_PREFIX}${sortTestSuffix}-aaa`;
			zzzVarName = `${SORT_PREFIX}${sortTestSuffix}-zzz`;

			await cleanupVariables(apiClient, SORT_PREFIX);
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

		test.afterEach(async ({ apiClient }) => {
			await cleanupVariables(apiClient, SORT_PREFIX);
		});

		test("should sort variables by name A to Z", async ({ page }) => {
			await expect(async () => {
				await page.goto(`/variables?name=${SORT_PREFIX}${sortTestSuffix}`);
				await expect(page.getByText(aaaVarName)).toBeVisible({ timeout: 2000 });
			}).toPass({ timeout: 15000 });

			await page
				.getByRole("combobox", { name: /variable sort order/i })
				.click();
			await page.getByRole("option", { name: "A to Z" }).click();

			await expect(page).toHaveURL(/sort=NAME_ASC/);

			const firstRow = page.getByRole("row").nth(1);
			await expect(firstRow).toContainText(aaaVarName);
		});

		test("should sort variables by name Z to A", async ({ page }) => {
			await expect(async () => {
				await page.goto(`/variables?name=${SORT_PREFIX}${sortTestSuffix}`);
				await expect(page.getByText(aaaVarName)).toBeVisible({ timeout: 2000 });
			}).toPass({ timeout: 15000 });

			await page
				.getByRole("combobox", { name: /variable sort order/i })
				.click();
			await page.getByRole("option", { name: "Z to A" }).click();

			await expect(page).toHaveURL(/sort=NAME_DESC/);

			const firstRow = page.getByRole("row").nth(1);
			await expect(firstRow).toContainText(zzzVarName);
		});

		test("should sort variables by created date (default)", async ({
			page,
		}) => {
			await expect(async () => {
				await page.goto(`/variables?name=${SORT_PREFIX}${sortTestSuffix}`);
				await expect(page.getByText(zzzVarName)).toBeVisible({ timeout: 2000 });
			}).toPass({ timeout: 15000 });

			await expect(page).toHaveURL(/sort=CREATED_DESC/);

			const firstRow = page.getByRole("row").nth(1);
			await expect(firstRow).toContainText(zzzVarName);
		});
	});

	test.describe("Pagination", () => {
		const PAGE_PREFIX = "e2e-page-";
		let paginationTestSuffix: string;

		test.beforeEach(async ({ apiClient }) => {
			paginationTestSuffix = `${Date.now()}`;

			await cleanupVariables(apiClient, PAGE_PREFIX);
			const createPromises = [];
			for (let i = 0; i < 15; i++) {
				createPromises.push(
					createVariable(apiClient, {
						name: `${PAGE_PREFIX}${paginationTestSuffix}-${String(i).padStart(2, "0")}`,
						value: `value-${i}`,
					}),
				);
			}
			await Promise.all(createPromises);
		});

		test.afterEach(async ({ apiClient }) => {
			await cleanupVariables(apiClient, PAGE_PREFIX);
		});

		test("should show correct page count", async ({ page }) => {
			await expect(async () => {
				await page.goto(
					`/variables?name=${PAGE_PREFIX}${paginationTestSuffix}`,
				);
				await expect(page.getByText("Page 1 of 2")).toBeVisible({
					timeout: 2000,
				});
			}).toPass({ timeout: 15000 });
		});

		test("should navigate to next page", async ({ page }) => {
			await expect(async () => {
				await page.goto(
					`/variables?name=${PAGE_PREFIX}${paginationTestSuffix}`,
				);
				await expect(page.getByText("Page 1 of 2")).toBeVisible({
					timeout: 2000,
				});
			}).toPass({ timeout: 15000 });

			await page.getByRole("button", { name: "Go to next page" }).click();

			await expect(page.getByText("Page 2 of 2")).toBeVisible();
			await expect(page).toHaveURL(/offset=10/);
		});

		test("should navigate to previous page", async ({ page }) => {
			await expect(async () => {
				await page.goto(
					`/variables?name=${PAGE_PREFIX}${paginationTestSuffix}&offset=10&limit=10&sort=CREATED_DESC`,
				);
				await expect(page.getByText("Page 2 of 2")).toBeVisible({
					timeout: 2000,
				});
			}).toPass({ timeout: 15000 });

			await page.getByRole("button", { name: "Go to previous page" }).click();

			await expect(page.getByText("Page 1 of 2")).toBeVisible();
			await expect(page).toHaveURL(/offset=0/);
		});

		test("should change items per page", async ({ page }) => {
			await expect(async () => {
				await page.goto(
					`/variables?name=${PAGE_PREFIX}${paginationTestSuffix}`,
				);
				await expect(page.getByText("Page 1 of 2")).toBeVisible({
					timeout: 2000,
				});
			}).toPass({ timeout: 15000 });

			await page.getByRole("combobox", { name: "Items per page" }).click();
			await page.getByRole("option", { name: "25" }).click();

			await expect(page.getByText("Page 1 of 1")).toBeVisible();
			await expect(page).toHaveURL(/limit=25/);
		});

		test("should disable previous buttons on first page", async ({ page }) => {
			await expect(async () => {
				await page.goto(
					`/variables?name=${PAGE_PREFIX}${paginationTestSuffix}`,
				);
				await expect(page.getByText("Page 1 of 2")).toBeVisible({
					timeout: 2000,
				});
			}).toPass({ timeout: 15000 });

			await expect(
				page.getByRole("button", { name: "Go to first page" }),
			).toBeDisabled();
			await expect(
				page.getByRole("button", { name: "Go to previous page" }),
			).toBeDisabled();

			await expect(
				page.getByRole("button", { name: "Go to next page" }),
			).toBeEnabled();
			await expect(
				page.getByRole("button", { name: "Go to last page" }),
			).toBeEnabled();
		});

		test("should disable next buttons on last page", async ({ page }) => {
			await expect(async () => {
				await page.goto(
					`/variables?name=${PAGE_PREFIX}${paginationTestSuffix}&offset=10&limit=10&sort=CREATED_DESC`,
				);
				await expect(page.getByText("Page 2 of 2")).toBeVisible({
					timeout: 2000,
				});
			}).toPass({ timeout: 15000 });

			await expect(
				page.getByRole("button", { name: "Go to next page" }),
			).toBeDisabled();
			await expect(
				page.getByRole("button", { name: "Go to last page" }),
			).toBeDisabled();

			await expect(
				page.getByRole("button", { name: "Go to first page" }),
			).toBeEnabled();
			await expect(
				page.getByRole("button", { name: "Go to previous page" }),
			).toBeEnabled();
		});
	});
});
