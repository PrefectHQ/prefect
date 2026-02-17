import type { Page } from "@playwright/test";
import {
	cleanupArtifacts,
	cleanupFlowRuns,
	cleanupFlows,
	createFlow,
	createFlowRun,
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
			.getByText("Create an artifact to get started")
			.or(page.getByText(/\d+ artifact/i)),
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
		try {
			await cleanupFlowRuns(apiClient, LIST_PREFIX);
		} catch {
			// Ignore cleanup errors
		}
		try {
			await cleanupFlows(apiClient, LIST_PREFIX);
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
			page.getByText("Create an artifact to get started"),
		).toBeVisible();
		await expect(
			page.getByText(/artifacts are byproducts of your runs/i),
		).toBeVisible();
	});

	test("Displays artifacts in list with key, type, and flow run link", async ({
		page,
		apiClient,
	}) => {
		const timestamp = Date.now();
		const flow = await createFlow(apiClient, `${LIST_PREFIX}flow-${timestamp}`);
		const flowRunName = `${LIST_PREFIX}run-${timestamp}`;
		const flowRun = await createFlowRun(apiClient, {
			flowId: flow.id,
			name: flowRunName,
			state: { type: "COMPLETED", name: "Completed" },
		});

		const mdKey = `${LIST_PREFIX}md-${timestamp}`;
		await createMarkdownArtifact(apiClient, {
			key: mdKey,
			markdown: "# Test",
			flowRunId: flowRun.id,
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

		await expect(page.getByText("MARKDOWN")).toBeVisible();

		await expect(page.getByText(flowRunName)).toBeVisible();
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

		await page.getByRole("combobox", { name: /artifact type/i }).click();
		await page.getByRole("option", { name: "Table" }).click();

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
