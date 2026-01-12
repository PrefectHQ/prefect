import {
	cleanupVariables,
	createVariable,
	expect,
	listVariables,
	test,
	waitForServerHealth,
} from "../fixtures";

const TEST_PREFIX = "e2e-test-";

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

			// Verify via API
			const variables = await listVariables(apiClient);
			const created = variables.find((v) => v.name === variableName);
			expect(created).toBeDefined();
			expect(created?.value).toEqual(variableValue);
		});

		test("should create a variable with tags", async ({ page, apiClient }) => {
			const variableName = `${TEST_PREFIX}tagged-var-${Date.now()}`;
			const tags = ["production", "config"];

			await page.goto("/variables");

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

			await page.getByRole("button", { name: /add variable/i }).click();

			const dialog = page.getByRole("dialog", { name: /new variable/i });
			await expect(dialog).toBeVisible();

			// Click the Close button in the dialog footer (not the X button in the corner)
			await dialog
				.locator("form")
				.getByRole("button", { name: /close/i })
				.click();

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

			await page.goto("/variables");

			// Wait for variable to appear
			await expect(page.getByText(variableName)).toBeVisible();

			// Click actions menu
			await page.getByRole("button", { name: /open menu/i }).click();
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

			await page.goto("/variables");

			// Wait for variable to appear
			await expect(page.getByText(variableName)).toBeVisible();

			// Click actions menu and delete
			await page.getByRole("button", { name: /open menu/i }).click();
			await page.getByRole("menuitem", { name: /delete/i }).click();

			// Wait for variable to be removed from list
			await expect(page.getByText(variableName)).not.toBeVisible();

			// Verify via API
			const variables = await listVariables(apiClient);
			const deleted = variables.find((v) => v.name === variableName);
			expect(deleted).toBeUndefined();
		});
	});
});
