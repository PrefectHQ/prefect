import type { Page } from "@playwright/test";
import {
	cleanupDeployments,
	cleanupFlowRuns,
	cleanupFlows,
	createDeployment,
	createFlow,
	expect,
	listFlowRuns,
	test,
	waitForServerHealth,
} from "../fixtures";

const TEST_PREFIX = "e2e-flows-list-";

async function waitForFlowsPageReady(page: Page): Promise<void> {
	await expect(
		page
			.getByRole("heading", { name: /run a flow to get started/i })
			.or(page.getByText(/\d+ Flows?/)),
	).toBeVisible({ timeout: 10000 });
}

test.describe("Flows List Page", () => {
	test.describe.configure({ mode: "serial" });

	test.beforeAll(async ({ apiClient }) => {
		await waitForServerHealth(apiClient);
	});

	test.beforeEach(async ({ apiClient }) => {
		try {
			await cleanupFlows(apiClient, TEST_PREFIX);
			await cleanupFlowRuns(apiClient, TEST_PREFIX);
			await cleanupDeployments(apiClient, TEST_PREFIX);
		} catch {
			// Ignore cleanup errors
		}
	});

	test.afterEach(async ({ apiClient }) => {
		try {
			await cleanupFlows(apiClient, TEST_PREFIX);
			await cleanupFlowRuns(apiClient, TEST_PREFIX);
			await cleanupDeployments(apiClient, TEST_PREFIX);
		} catch {
			// Ignore cleanup errors
		}
	});

	test("Empty state when no flows exist", async ({ page }) => {
		await page.goto("/flows");

		const emptyStateHeading = page.getByRole("heading", {
			name: /run a flow to get started/i,
		});
		const flowsCount = page.getByText(/\d+ Flows?/);

		await expect(emptyStateHeading.or(flowsCount)).toBeVisible({
			timeout: 10000,
		});

		if (await emptyStateHeading.isVisible()) {
			await expect(page.getByText(/flows are python functions/i)).toBeVisible();
			await expect(
				page.getByRole("link", { name: /view docs/i }),
			).toBeVisible();
		} else {
			test.skip(true, "Flows already exist from other tests");
		}
	});

	test("Flows list with name search", async ({ page, apiClient }) => {
		const flowName = `${TEST_PREFIX}search-${Date.now()}`;
		await createFlow(apiClient, flowName);

		await expect(async () => {
			await page.goto("/flows");
			await expect(page.getByText(/\d+ Flows?/)).toBeVisible({
				timeout: 2000,
			});
		}).toPass({ timeout: 15000 });

		await page.getByPlaceholder("Flow names").fill(flowName);

		await expect(page).toHaveURL(/name=/);
		await expect(page.getByRole("link", { name: flowName })).toBeVisible();
	});

	test("Tag filter", async ({ page, apiClient }) => {
		const flowName = `${TEST_PREFIX}tag-${Date.now()}`;
		await createFlow(apiClient, { name: flowName, tags: ["e2e-tag-test"] });

		await expect(async () => {
			await page.goto("/flows");
			await expect(page.getByText(/\d+ Flows?/)).toBeVisible({
				timeout: 2000,
			});
		}).toPass({ timeout: 15000 });

		const tagsInput = page.getByPlaceholder("Filter by tags");
		await tagsInput.pressSequentially("e2e-tag-test");
		await page.keyboard.press("Enter");

		await expect(page).toHaveURL(/tags=/);
		await expect(page.getByRole("link", { name: flowName })).toBeVisible({
			timeout: 10000,
		});
	});

	test("Sort flows with URL persistence", async ({ page, apiClient }) => {
		const flowName = `${TEST_PREFIX}sort-${Date.now()}`;
		await createFlow(apiClient, flowName);

		await page.goto("/flows");
		await waitForFlowsPageReady(page);

		await page.getByLabel("Flow sort order").click();
		await page.getByRole("option", { name: "Z to A" }).click();

		await expect(page).toHaveURL(/sort=NAME_DESC/);
	});

	test("Pagination", async ({ page, apiClient }) => {
		const timestamp = Date.now();
		for (let i = 0; i < 6; i++) {
			await createFlow(
				apiClient,
				`${TEST_PREFIX}page-${timestamp}-${String(i).padStart(2, "0")}`,
			);
		}

		await expect(async () => {
			await page.goto(
				`/flows?limit=5&name=${encodeURIComponent(`${TEST_PREFIX}page-${timestamp}`)}`,
			);
			await expect(page.getByText(/Page 1 of 2/)).toBeVisible({
				timeout: 2000,
			});
		}).toPass({ timeout: 15000 });

		await page.getByRole("button", { name: /go to next page/i }).click();

		await expect(page).toHaveURL(/page=2/);
		await expect(page.getByText(/Page 2 of/)).toBeVisible();
	});

	test("Navigate from list to flow detail", async ({ page, apiClient }) => {
		const flowName = `${TEST_PREFIX}detail-${Date.now()}`;
		const flow = await createFlow(apiClient, flowName);

		await expect(async () => {
			await page.goto(`/flows?name=${flowName}`);
			await expect(page.getByText(flowName)).toBeVisible({
				timeout: 2000,
			});
		}).toPass({ timeout: 15000 });

		await page.getByRole("link", { name: flowName }).click();

		await expect(page).toHaveURL(new RegExp(`/flows/flow/${flow.id}`));
		await expect(page.getByText(flowName)).toBeVisible();
	});

	test("Deployment count in list", async ({ page, apiClient }) => {
		const flowName = `${TEST_PREFIX}deploy-${Date.now()}`;
		const flow = await createFlow(apiClient, flowName);

		await expect(async () => {
			const dep = await createDeployment(apiClient, {
				name: `${TEST_PREFIX}dep-${Date.now()}`,
				flowId: flow.id,
			});
			if (!dep) throw new Error("Deployment creation returned empty");
		}).toPass({ timeout: 15000 });

		await expect(async () => {
			await page.goto(`/flows?name=${flowName}`);
			await expect(page.getByRole("link", { name: flowName })).toBeVisible({
				timeout: 2000,
			});
		}).toPass({ timeout: 15000 });

		await expect(page.getByText("1 Deployment")).toBeVisible({
			timeout: 10000,
		});
	});

	test("Run button disabled for a flow with no deployments", async ({
		page,
		apiClient,
	}) => {
		const flowName = `${TEST_PREFIX}no-deps-${Date.now()}`;
		await createFlow(apiClient, flowName);

		await expect(async () => {
			await page.goto(`/flows?name=${flowName}`);
			await expect(page.getByRole("link", { name: flowName })).toBeVisible({
				timeout: 2000,
			});
		}).toPass({ timeout: 15000 });

		const row = page.getByRole("row", { name: new RegExp(flowName) });
		const runButton = row.getByRole("button", { name: "Run" });
		await expect(runButton).toBeVisible();
		await expect(runButton).toBeDisabled();
	});

	test("Run a flow from the list via an explicitly selected deployment", async ({
		page,
		apiClient,
	}) => {
		const timestamp = Date.now();
		const flowName = `${TEST_PREFIX}run-${timestamp}`;
		const flow = await createFlow(apiClient, flowName);
		await createDeployment(apiClient, {
			name: `${TEST_PREFIX}dep-a-${timestamp}`,
			flowId: flow.id,
		});
		const depB = await createDeployment(apiClient, {
			name: `${TEST_PREFIX}dep-b-${timestamp}`,
			flowId: flow.id,
		});

		await expect(async () => {
			await page.goto(`/flows?name=${flowName}`);
			await expect(page.getByRole("link", { name: flowName })).toBeVisible({
				timeout: 2000,
			});
		}).toPass({ timeout: 15000 });

		const row = page.getByRole("row", { name: new RegExp(flowName) });
		const runButton = row.getByRole("button", { name: "Run" });
		await expect(runButton).toBeEnabled({ timeout: 10000 });
		await runButton.click();

		const dialog = page.getByRole("dialog", { name: `Run ${flowName}` });
		await expect(dialog).toBeVisible();

		await dialog.getByRole("button", { name: "Select a deployment" }).click();
		await page
			.getByRole("option", { name: `${TEST_PREFIX}dep-b-${timestamp}` })
			.click();

		await dialog.getByRole("button", { name: "Run" }).click();
		await page.getByRole("menuitem", { name: "Quick run" }).click();

		await expect(page.getByRole("button", { name: /view run/i })).toBeVisible({
			timeout: 10000,
		});
		await expect(dialog).not.toBeVisible();
		await expect(page).toHaveURL(/\/flows/);

		await expect
			.poll(
				async () => {
					const flowRuns = await listFlowRuns(apiClient);
					return flowRuns.find(
						(fr) => fr.deployment_id === depB.id && fr.flow_id === flow.id,
					);
				},
				{ timeout: 10000 },
			)
			.toBeTruthy();
	});
});
