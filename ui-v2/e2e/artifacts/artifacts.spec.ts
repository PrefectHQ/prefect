import type { Page } from "@playwright/test";
import {
	cleanupArtifacts,
	cleanupFlowRuns,
	cleanupFlows,
	createFlow,
	createFlowRun,
	createLinkArtifact,
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

		// Use toPass retry pattern to handle slow page loads under CI load
		await expect(async () => {
			await page.goto("/artifacts");
			await waitForArtifactsPageReady(page);
		}).toPass({ timeout: 15000 });

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

const DETAIL_PREFIX = "e2e-art-detail-";

test.describe("Artifact Detail and Navigation", () => {
	test.describe.configure({ mode: "serial" });

	test.beforeAll(async ({ apiClient }) => {
		await waitForServerHealth(apiClient);
	});

	test.beforeEach(async ({ apiClient }) => {
		try {
			await cleanupArtifacts(apiClient, DETAIL_PREFIX);
		} catch {
			// Ignore cleanup errors
		}
	});

	test.afterAll(async ({ apiClient }) => {
		try {
			await cleanupArtifacts(apiClient, DETAIL_PREFIX);
		} catch {
			// Ignore cleanup errors
		}
		try {
			await cleanupFlowRuns(apiClient, DETAIL_PREFIX);
		} catch {
			// Ignore cleanup errors
		}
		try {
			await cleanupFlows(apiClient, DETAIL_PREFIX);
		} catch {
			// Ignore cleanup errors
		}
	});

	test("Navigate from list to key page to detail page", async ({
		page,
		apiClient,
	}) => {
		const timestamp = Date.now();
		const artifactKey = `${DETAIL_PREFIX}nav-${timestamp}`;
		const artifact = await createMarkdownArtifact(apiClient, {
			key: artifactKey,
			markdown: "# Navigation Test",
		});

		await expect(async () => {
			await page.goto("/artifacts");
			await expect(page.getByText(artifactKey)).toBeVisible({
				timeout: 2000,
			});
		}).toPass({ timeout: 15000 });

		await page.getByText(artifactKey).first().click();

		await expect(page).toHaveURL(new RegExp(`/artifacts/key/${artifactKey}`), {
			timeout: 10000,
		});

		await expect(
			page.getByLabel("breadcrumb").getByText(artifactKey),
		).toBeVisible();

		const timelineCard = page.getByTestId(`timeline-card-${artifact.id}`);
		await expect(timelineCard).toBeVisible({ timeout: 10000 });
		await timelineCard.getByRole("link").first().click();

		await expect(page).toHaveURL(
			new RegExp(`/artifacts/artifact/${artifact.id}`),
			{ timeout: 10000 },
		);

		await expect(
			page.getByLabel("breadcrumb").getByText(artifactKey),
		).toBeVisible();
	});

	test("Render artifact content correctly for all 3 types", async ({
		page,
		apiClient,
	}) => {
		const timestamp = Date.now();

		// Part A - Markdown
		const mdKey = `${DETAIL_PREFIX}render-md-${timestamp}`;
		const mdArtifact = await createMarkdownArtifact(apiClient, {
			key: mdKey,
			markdown:
				"## Test Heading\n\nThis is **bold** text and some normal text.",
		});

		await expect(async () => {
			await page.goto(`/artifacts/key/${mdKey}`);
			await expect(
				page.getByTestId(`timeline-card-${mdArtifact.id}`),
			).toBeVisible({ timeout: 2000 });
		}).toPass({ timeout: 15000 });

		await page
			.getByTestId(`timeline-card-${mdArtifact.id}`)
			.getByRole("link")
			.first()
			.click();

		await expect(page).toHaveURL(
			new RegExp(`/artifacts/artifact/${mdArtifact.id}`),
			{ timeout: 10000 },
		);

		const mdDisplay = page.getByTestId("markdown-display");
		await expect(mdDisplay).toBeVisible({ timeout: 10000 });
		await expect(
			mdDisplay.locator("h2", { hasText: "Test Heading" }),
		).toBeVisible();
		await expect(
			mdDisplay.locator("strong", { hasText: "bold" }),
		).toBeVisible();

		// Part B - Table
		const tblKey = `${DETAIL_PREFIX}render-tbl-${timestamp}`;
		const tblArtifact = await createTableArtifact(apiClient, {
			key: tblKey,
			table: [
				{ id: "1", name: "Alice", score: "95" },
				{ id: "2", name: "Bob", score: "87" },
				{ id: "3", name: "Charlie", score: "92" },
			],
		});

		await expect(async () => {
			await page.goto(`/artifacts/key/${tblKey}`);
			await expect(
				page.getByTestId(`timeline-card-${tblArtifact.id}`),
			).toBeVisible({ timeout: 2000 });
		}).toPass({ timeout: 15000 });

		await page
			.getByTestId(`timeline-card-${tblArtifact.id}`)
			.getByRole("link")
			.first()
			.click();

		await expect(page).toHaveURL(
			new RegExp(`/artifacts/artifact/${tblArtifact.id}`),
			{ timeout: 10000 },
		);

		const tblDisplay = page.getByTestId("table-display");
		await expect(tblDisplay).toBeVisible({ timeout: 10000 });
		await expect(
			tblDisplay.getByRole("columnheader", { name: "name" }),
		).toBeVisible();
		await expect(
			tblDisplay.getByRole("columnheader", { name: "score" }),
		).toBeVisible();
		await expect(tblDisplay.getByRole("cell", { name: "Alice" })).toBeVisible();
		await expect(tblDisplay.getByRole("cell", { name: "Bob" })).toBeVisible();
		await expect(
			tblDisplay.getByRole("cell", { name: "Charlie" }),
		).toBeVisible();
		await expect(tblDisplay.getByRole("row")).toHaveCount(4); // 1 header + 3 data rows

		// Part C - Link (stored as markdown type)
		const linkKey = `${DETAIL_PREFIX}render-link-${timestamp}`;
		const linkArtifact = await createLinkArtifact(apiClient, {
			key: linkKey,
			link: "https://docs.prefect.io",
			linkText: "Prefect Docs",
		});

		await expect(async () => {
			await page.goto(`/artifacts/key/${linkKey}`);
			await expect(
				page.getByTestId(`timeline-card-${linkArtifact.id}`),
			).toBeVisible({ timeout: 2000 });
		}).toPass({ timeout: 15000 });

		await page
			.getByTestId(`timeline-card-${linkArtifact.id}`)
			.getByRole("link")
			.first()
			.click();

		await expect(page).toHaveURL(
			new RegExp(`/artifacts/artifact/${linkArtifact.id}`),
			{ timeout: 10000 },
		);

		const linkDisplay = page.getByTestId("markdown-display");
		await expect(linkDisplay).toBeVisible({ timeout: 10000 });
		const anchor = linkDisplay.getByRole("link", { name: "Prefect Docs" });
		await expect(anchor).toBeVisible();
		await expect(anchor).toHaveAttribute("href", "https://docs.prefect.io");
	});

	test("Navigate to flow run from artifact", async ({ page, apiClient }) => {
		const timestamp = Date.now();

		const flow = await createFlow(
			apiClient,
			`${DETAIL_PREFIX}flow-${timestamp}`,
		);
		const flowRunName = `${DETAIL_PREFIX}run-${timestamp}`;
		const flowRun = await createFlowRun(apiClient, {
			flowId: flow.id,
			name: flowRunName,
			state: { type: "COMPLETED", name: "Completed" },
		});

		const artifactKey = `${DETAIL_PREFIX}linked-${timestamp}`;
		await createMarkdownArtifact(apiClient, {
			key: artifactKey,
			markdown: "# Linked to flow",
			flowRunId: flowRun.id,
		});

		await expect(async () => {
			await page.goto(`/artifacts/key/${artifactKey}`);
			await expect(page.getByText(flowRunName)).toBeVisible({
				timeout: 2000,
			});
		}).toPass({ timeout: 15000 });

		await page.getByRole("link", { name: flowRunName }).click();

		await expect(page).toHaveURL(new RegExp(`/runs/flow-run/${flowRun.id}`), {
			timeout: 10000,
		});
	});

	test("Latest artifact shown when multiple share same key", async ({
		page,
		apiClient,
	}) => {
		const timestamp = Date.now();
		const sharedKey = `${DETAIL_PREFIX}same-key-${timestamp}`;

		const v1 = await createMarkdownArtifact(apiClient, {
			key: sharedKey,
			markdown: "# Version One",
		});
		await new Promise((r) => setTimeout(r, 100));
		const v2 = await createMarkdownArtifact(apiClient, {
			key: sharedKey,
			markdown: "# Version Two",
		});
		await new Promise((r) => setTimeout(r, 100));
		const v3 = await createMarkdownArtifact(apiClient, {
			key: sharedKey,
			markdown: "# Version Three",
		});

		await expect(async () => {
			await page.goto("/artifacts");
			await expect(page.getByText(sharedKey)).toBeVisible({
				timeout: 2000,
			});
		}).toPass({ timeout: 15000 });

		await page.getByText(sharedKey).first().click();

		await expect(page).toHaveURL(new RegExp(`/artifacts/key/${sharedKey}`), {
			timeout: 10000,
		});

		await expect(page.getByTestId(`timeline-card-${v1.id}`)).toBeVisible({
			timeout: 10000,
		});
		await expect(page.getByTestId(`timeline-card-${v2.id}`)).toBeVisible();
		await expect(page.getByTestId(`timeline-card-${v3.id}`)).toBeVisible();

		// Timeline is sorted CREATED_DESC, so v3 (latest) is first
		await page
			.getByTestId(`timeline-card-${v3.id}`)
			.getByRole("link")
			.first()
			.click();

		await expect(page).toHaveURL(new RegExp(`/artifacts/artifact/${v3.id}`), {
			timeout: 10000,
		});

		const mdDisplay = page.getByTestId("markdown-display");
		await expect(mdDisplay).toBeVisible({ timeout: 10000 });
		await expect(
			mdDisplay.getByRole("heading", { name: "Version Three" }),
		).toBeVisible();

		// Go back to key page and click v1
		await page.goBack();
		await expect(page).toHaveURL(new RegExp(`/artifacts/key/${sharedKey}`), {
			timeout: 10000,
		});

		await page
			.getByTestId(`timeline-card-${v1.id}`)
			.getByRole("link")
			.first()
			.click();

		await expect(page).toHaveURL(new RegExp(`/artifacts/artifact/${v1.id}`), {
			timeout: 10000,
		});

		const mdDisplayV1 = page.getByTestId("markdown-display");
		await expect(mdDisplayV1).toBeVisible({ timeout: 10000 });
		await expect(
			mdDisplayV1.getByRole("heading", { name: "Version One" }),
		).toBeVisible();
		await expect(
			mdDisplayV1.getByRole("heading", { name: "Version Three" }),
		).not.toBeVisible();
	});
});
