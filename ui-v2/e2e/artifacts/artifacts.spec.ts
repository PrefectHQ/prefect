import type { Page } from "@playwright/test";
import {
	cleanupArtifacts,
	createMarkdownArtifact,
	createTableArtifact,
	expect,
	listArtifacts,
	test,
	waitForServerHealth,
} from "../fixtures";

const LIST_PREFIX = "e2e-art-list-";

async function waitForArtifactsPageReady(page: Page): Promise<void> {
	await expect(
		page
			.getByRole("heading", { name: /create an artifact to get started/i })
			.or(page.getByRole("heading", { name: /artifacts/i })),
	).toBeVisible({ timeout: 10000 });
}

test.describe("Artifacts List Page", () => {
	test.describe.configure({ mode: "serial" });

	test.beforeAll(async ({ apiClient }) => {
		await waitForServerHealth(apiClient);
	});

	test.beforeEach(async ({ apiClient }) => {
		try {
			await cleanupArtifacts(apiClient, LIST_PREFIX);
		} catch {
			// Ignore cleanup errors
		}
	});

	test.afterAll(async ({ apiClient }) => {
		try {
			await cleanupArtifacts(apiClient, LIST_PREFIX);
		} catch {
			// Ignore cleanup errors
		}
	});

	test("Empty state when no artifacts exist", async ({ page, apiClient }) => {
		const artifacts = await listArtifacts(apiClient);
		test.skip(artifacts.length > 0, "Artifacts already exist from other tests");

		await page.goto("/artifacts");
		await waitForArtifactsPageReady(page);

		await expect(
			page.getByRole("heading", {
				name: /create an artifact to get started/i,
			}),
		).toBeVisible();
		await expect(
			page.getByText(/artifacts are byproducts of your runs/i),
		).toBeVisible();
	});

	test("Displays artifacts in list with key and type", async ({
		page,
		apiClient,
	}) => {
		const timestamp = Date.now();

		const mdKey = `${LIST_PREFIX}md-${timestamp}`;
		await createMarkdownArtifact(apiClient, {
			key: mdKey,
			markdown: "# Test",
		});

		const tblKey = `${LIST_PREFIX}tbl-${timestamp}`;
		await createTableArtifact(apiClient, {
			key: tblKey,
			table: [{ id: "1", name: "Alice" }],
		});

		await expect(async () => {
			await page.goto("/artifacts");
			await expect(page.getByText(mdKey)).toBeVisible({ timeout: 2000 });
		}).toPass({ timeout: 15000 });

		await expect(page.getByText(mdKey)).toBeVisible();
		await expect(page.getByText(tblKey)).toBeVisible();

		await expect(page.getByText("MARKDOWN").first()).toBeVisible();
		await expect(page.getByText("TABLE").first()).toBeVisible();
	});

	test("Filters artifacts by type", async ({ page, apiClient }) => {
		const timestamp = Date.now();
		const mdKey = `${LIST_PREFIX}filter-md-${timestamp}`;
		const tblKey = `${LIST_PREFIX}filter-tbl-${timestamp}`;

		await createMarkdownArtifact(apiClient, {
			key: mdKey,
			markdown: "# Filter test",
		});
		await createTableArtifact(apiClient, {
			key: tblKey,
			table: [{ id: "1", value: "test" }],
		});

		await expect(async () => {
			await page.goto("/artifacts");
			await expect(page.getByText(mdKey)).toBeVisible({ timeout: 2000 });
			await expect(page.getByText(tblKey)).toBeVisible({ timeout: 2000 });
		}).toPass({ timeout: 15000 });

		await page.getByLabel("Artifact type").click();
		await page.getByText("Table", { exact: true }).click();

		await expect(page).toHaveURL(/type=table/, { timeout: 5000 });

		await expect(page.getByText(tblKey)).toBeVisible();
		await expect(page.getByText(mdKey)).not.toBeVisible();
	});

	test("Shows artifact count in list", async ({ page, apiClient }) => {
		const timestamp = Date.now();
		await createMarkdownArtifact(apiClient, {
			key: `${LIST_PREFIX}count-a-${timestamp}`,
			markdown: "# Count A",
		});
		await createMarkdownArtifact(apiClient, {
			key: `${LIST_PREFIX}count-b-${timestamp}`,
			markdown: "# Count B",
		});

		await expect(async () => {
			await page.goto("/artifacts");
			await expect(
				page.getByText(`${LIST_PREFIX}count-a-${timestamp}`),
			).toBeVisible({ timeout: 2000 });
		}).toPass({ timeout: 15000 });

		await expect(page.getByText(/\d+ artifact/i)).toBeVisible();
	});
});
