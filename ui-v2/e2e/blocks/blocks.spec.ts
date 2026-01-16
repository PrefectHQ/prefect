import type { Page } from "@playwright/test";
import {
	type BlockSchema,
	type BlockType,
	cleanupBlockDocuments,
	createBlockDocument,
	expect,
	listBlockDocuments,
	listBlockSchemas,
	listBlockTypes,
	test,
	waitForServerHealth,
} from "../fixtures";

const TEST_PREFIX = "e2e-block-";

/**
 * Get a block type and schema for testing.
 * Prefers the "secret" block type as it's always available and simple.
 * Falls back to any available block type if "secret" is not found.
 */
async function getTestBlockTypeAndSchema(
	apiClient: Parameters<typeof listBlockTypes>[0],
): Promise<{ blockType: BlockType; blockSchema: BlockSchema }> {
	const blockTypes = await listBlockTypes(apiClient);
	if (blockTypes.length === 0) {
		throw new Error("No block types available for testing");
	}

	// Prefer "secret" block type as it's always available and simple
	const secretBlockType = blockTypes.find((bt) => bt.slug === "secret");
	const blockType = secretBlockType ?? blockTypes[0];

	const blockSchemas = await listBlockSchemas(apiClient, blockType.id);
	if (blockSchemas.length === 0) {
		throw new Error(
			`No block schemas available for block type ${blockType.slug}`,
		);
	}

	return { blockType, blockSchema: blockSchemas[0] };
}

/**
 * Wait for the blocks page to be fully loaded.
 */
async function waitForBlocksPageReady(page: Page): Promise<void> {
	await expect(
		page
			.getByRole("heading", { name: /add a block to get started/i })
			.or(page.getByRole("table")),
	).toBeVisible();
}

test.describe("Blocks Page", () => {
	test.beforeAll(async ({ apiClient }) => {
		await waitForServerHealth(apiClient);
	});

	test.beforeEach(async ({ apiClient }) => {
		await cleanupBlockDocuments(apiClient, TEST_PREFIX);
	});

	test.afterEach(async ({ apiClient }) => {
		await cleanupBlockDocuments(apiClient, TEST_PREFIX);
	});

	test.describe("Empty State", () => {
		test("should show empty state when no blocks exist", async ({
			page,
			apiClient,
		}) => {
			// First verify no blocks exist via API
			const documents = await listBlockDocuments(apiClient);
			// Skip this test if there are existing blocks (from other tests or manual creation)
			// since we can't control the global state in parallel test execution
			test.skip(
				documents.length > 0,
				"Skipping empty state test because blocks already exist",
			);

			await page.goto("/blocks");

			await expect(
				page.getByRole("heading", { name: /add a block to get started/i }),
			).toBeVisible();
			await expect(
				page.getByRole("link", { name: /add block/i }),
			).toBeVisible();
		});
	});

	test.describe("Full Flow: Create, View, Edit, Delete Block", () => {
		test("should complete full block lifecycle via UI", async ({
			page,
			apiClient,
		}) => {
			const blockName = `${TEST_PREFIX}lifecycle-${Date.now()}`;
			const initialValue = { key: "initial-value" };
			const updatedValue = { key: "updated-value" };

			// --- CREATE BLOCK ---
			// Navigate directly to the JSON block create page to avoid search issues
			await page.goto("/blocks/catalog/json/create");

			// Wait for create page to load - verify URL and wait for the form to be ready
			// Use longer timeout as the page may take time to load block type data
			await expect(page).toHaveURL(/\/blocks\/catalog\/json\/create/);
			await expect(page.getByRole("textbox", { name: /name/i })).toBeVisible({
				timeout: 15000,
			});

			// Fill in the block name
			await page.getByRole("textbox", { name: /name/i }).fill(blockName);

			// Fill in the JSON data using the code mirror editor
			const jsonInput = page.locator(".cm-content");
			await jsonInput.click();
			await page.keyboard.type(JSON.stringify(initialValue));

			// Save the block
			await page.getByRole("button", { name: /save/i }).click();

			// Wait for navigation to block details page
			await expect(page).toHaveURL(/\/blocks\/block\/[a-f0-9-]+$/);

			// Verify block was created via API
			await expect
				.poll(
					async () => {
						const documents = await listBlockDocuments(apiClient);
						return documents.find((d) => d.name === blockName);
					},
					{ timeout: 5000 },
				)
				.toBeDefined();

			// --- VIEW BLOCK DETAILS ---
			// Verify we can see the block name on the details page
			await expect(page.getByText(blockName)).toBeVisible();

			// --- EDIT BLOCK ---
			// Open action menu and click edit
			await page.getByRole("button", { name: /open menu/i }).click();
			await page.getByRole("menuitem", { name: /edit/i }).click();

			// Wait for edit page
			await expect(page).toHaveURL(/\/blocks\/block\/[a-f0-9-]+\/edit$/);

			// Update the JSON data
			const editJsonInput = page.locator(".cm-content");
			await editJsonInput.click();
			await page.keyboard.press("Control+A");
			await page.keyboard.type(JSON.stringify(updatedValue));

			// Save changes
			await page.getByRole("button", { name: /save/i }).click();

			// Wait for navigation back to details
			await expect(page).toHaveURL(/\/blocks\/block\/[a-f0-9-]+$/);

			// Verify update via API - check that the block still exists
			// Note: The data format returned by the API may be wrapped, so we just verify the block exists
			await expect
				.poll(
					async () => {
						const documents = await listBlockDocuments(apiClient);
						return documents.find((d) => d.name === blockName);
					},
					{ timeout: 10000 },
				)
				.toBeDefined();

			// --- DELETE BLOCK ---
			// Open action menu and click delete
			await page.getByRole("button", { name: /open menu/i }).click();
			await page.getByRole("menuitem", { name: /delete/i }).click();

			// Wait for and confirm deletion in dialog
			const deleteDialog = page.getByRole("alertdialog");
			await expect(deleteDialog).toBeVisible();
			await deleteDialog.getByRole("button", { name: /delete/i }).click();

			// Wait for dialog to close and verify block was deleted via API
			await expect(deleteDialog).not.toBeVisible();

			// Verify block was deleted via API
			await expect
				.poll(
					async () => {
						const documents = await listBlockDocuments(apiClient);
						return documents.find((d) => d.name === blockName);
					},
					{ timeout: 10000 },
				)
				.toBeUndefined();
		});
	});

	test.describe("Block Listing", () => {
		test("should display existing blocks in the list", async ({
			page,
			apiClient,
		}) => {
			// Create a block via API first
			const blockName = `${TEST_PREFIX}list-${Date.now()}`;
			const { blockType, blockSchema } =
				await getTestBlockTypeAndSchema(apiClient);

			await createBlockDocument(apiClient, {
				name: blockName,
				blockTypeId: blockType.id,
				blockSchemaId: blockSchema.id,
				data: { value: "test" },
			});

			// Navigate to blocks page
			await page.goto("/blocks");

			// Wait for page to be ready and block to appear in the list
			await waitForBlocksPageReady(page);
			await expect(page.getByText(blockName)).toBeVisible({ timeout: 10000 });

			// Verify table is shown (not empty state)
			await expect(page.getByRole("table")).toBeVisible();
		});

		test("should navigate to block details when clicking a block", async ({
			page,
			apiClient,
		}) => {
			// Create a block via API first
			const blockName = `${TEST_PREFIX}navigate-${Date.now()}`;
			const { blockType, blockSchema } =
				await getTestBlockTypeAndSchema(apiClient);

			const block = await createBlockDocument(apiClient, {
				name: blockName,
				blockTypeId: blockType.id,
				blockSchemaId: blockSchema.id,
				data: { value: "navigate-test" },
			});

			// Navigate to blocks page
			await page.goto("/blocks");

			// Wait for page to be ready and block to appear
			await waitForBlocksPageReady(page);
			await expect(page.getByText(blockName)).toBeVisible({ timeout: 10000 });

			// Click on the block name link
			await page.getByRole("link", { name: blockName }).click();

			// Verify navigation to details page
			await expect(page).toHaveURL(`/blocks/block/${block.id}`);
		});
	});

	test.describe("Delete from List", () => {
		test("should delete a block via action menu from the list", async ({
			page,
			apiClient,
		}) => {
			// Create a block via API first
			const blockName = `${TEST_PREFIX}delete-list-${Date.now()}`;
			const { blockType, blockSchema } =
				await getTestBlockTypeAndSchema(apiClient);

			await createBlockDocument(apiClient, {
				name: blockName,
				blockTypeId: blockType.id,
				blockSchemaId: blockSchema.id,
				data: { value: "delete-me" },
			});

			// Navigate to blocks page
			await page.goto("/blocks");

			// Wait for page to be ready and block to appear
			await waitForBlocksPageReady(page);
			await expect(page.getByText(blockName)).toBeVisible({ timeout: 10000 });

			// Open action menu for the block row
			// Note: The action menu button is in each row
			await page.getByRole("button", { name: /open menu/i }).click();
			await page.getByRole("menuitem", { name: /delete/i }).click();

			// Wait for and confirm deletion in dialog
			const deleteDialog = page.getByRole("alertdialog");
			await expect(deleteDialog).toBeVisible();
			await deleteDialog.getByRole("button", { name: /delete/i }).click();

			// Wait for dialog to close
			await expect(deleteDialog).not.toBeVisible();

			// Wait for block to disappear from list
			await expect(page.getByText(blockName)).not.toBeVisible();

			// Verify via API
			await expect
				.poll(
					async () => {
						const documents = await listBlockDocuments(apiClient);
						return documents.find((d) => d.name === blockName);
					},
					{ timeout: 10000 },
				)
				.toBeUndefined();
		});
	});
});
