import {
	type BlockSchema,
	type BlockType,
	cleanupBlockDocuments,
	createBlockDocument,
	expect,
	listBlockSchemas,
	listBlockTypes,
	test,
	waitForServerHealth,
} from "../fixtures";

const TEST_PREFIX = "e2e-block-catalog-";

test.describe("Block Catalog", () => {
	test.beforeAll(async ({ apiClient }) => {
		await waitForServerHealth(apiClient);
	});

	test.beforeEach(async ({ apiClient }) => {
		await cleanupBlockDocuments(apiClient, TEST_PREFIX);
	});

	test.afterEach(async ({ apiClient }) => {
		await cleanupBlockDocuments(apiClient, TEST_PREFIX);
	});

	test("should view block types with names and descriptions (BCAT-01)", async ({
		page,
	}) => {
		await page.goto("/blocks/catalog");

		await expect(page.getByText(/\d+ Blocks?/)).toBeVisible();
		await expect(
			page.getByRole("heading", { name: "Secret", exact: true }),
		).toBeVisible();

		const detailsLinks = page.getByRole("link", { name: "Details" });
		await expect(detailsLinks.first()).toBeVisible();

		const createLinks = page.getByRole("link", { name: "Create" });
		await expect(createLinks.first()).toBeVisible();
	});

	test("should search block types and filter results (BCAT-02)", async ({
		page,
	}) => {
		await page.goto("/blocks/catalog");

		await expect(page.getByText(/\d+ Blocks?/)).toBeVisible();

		await page.getByPlaceholder("Search blocks").fill("secret");

		await expect(page).toHaveURL(/blockName=secret/);
		await expect(
			page.getByRole("heading", { name: "Secret", exact: true }),
		).toBeVisible();
	});

	test("should navigate to block type details page (BCAT-03)", async ({
		page,
	}) => {
		await page.goto("/blocks/catalog/secret");

		await expect(
			page.getByRole("heading", { name: "Secret", level: 3 }),
		).toBeVisible();

		await expect(page.locator(".prose")).toBeVisible();

		await expect(page.getByRole("link", { name: "Create" })).toBeVisible();
	});

	test("should create a block and verify via UI and API (BCAT-04)", async ({
		page,
		apiClient,
	}) => {
		const blockName = `${TEST_PREFIX}secret-${Date.now()}`;

		const blockTypes = await listBlockTypes(apiClient);
		const secretBlockType = blockTypes.find(
			(bt: BlockType) => bt.slug === "secret",
		);
		const blockType = secretBlockType ?? blockTypes[0];
		const blockSchemas = await listBlockSchemas(apiClient, blockType.id);
		const blockSchema: BlockSchema = blockSchemas[0];

		const block = await createBlockDocument(apiClient, {
			name: blockName,
			blockTypeId: blockType.id,
			blockSchemaId: blockSchema.id,
			data: { value: "test-secret-value" },
		});

		expect(block.id).toBeDefined();
		expect(block.name).toBe(blockName);

		await page.goto(`/blocks/block/${block.id}`);
		await expect(page.getByText(blockName)).toBeVisible({ timeout: 10000 });
	});
});
