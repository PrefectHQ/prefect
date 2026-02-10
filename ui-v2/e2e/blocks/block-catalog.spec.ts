import {
	cleanupBlockDocuments,
	expect,
	listBlockDocuments,
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

	test("should create a block with dual verification (BCAT-04)", async ({
		page,
		apiClient,
	}) => {
		const blockName = `${TEST_PREFIX}string-${Date.now()}`;

		await page.goto("/blocks/catalog/string/create");

		await page.getByLabel("Name").fill(blockName);

		await page.locator("textarea").fill("test-string-value");

		await page.getByRole("button", { name: /save/i }).click();

		await expect(page).toHaveURL(/\/blocks\/block\/[a-f0-9-]+$/, {
			timeout: 10000,
		});
		await expect(page.getByText(blockName)).toBeVisible({ timeout: 10000 });

		await expect
			.poll(
				async () => {
					const docs = await listBlockDocuments(apiClient);
					return docs.find((d) => d.name === blockName);
				},
				{ timeout: 30000 },
			)
			.toBeDefined();
	});
});
