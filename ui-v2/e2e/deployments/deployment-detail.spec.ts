import {
	cleanupDeployments,
	cleanupFlowRuns,
	cleanupFlows,
	createDeployment,
	createFlow,
	createFlowRun,
	expect,
	listDeployments,
	listFlowRuns,
	test,
	waitForServerHealth,
} from "../fixtures";

const TEST_PREFIX = "e2e-dep-detail-";

test.describe("Deployment Detail Page", () => {
	test.describe.configure({ mode: "serial" });

	test.beforeAll(async ({ apiClient }) => {
		await waitForServerHealth(apiClient);
	});

	test.beforeEach(async ({ apiClient }) => {
		try {
			await cleanupDeployments(apiClient, TEST_PREFIX);
			await cleanupFlowRuns(apiClient, TEST_PREFIX);
			await cleanupFlows(apiClient, TEST_PREFIX);
		} catch {
			// Ignore cleanup errors
		}
	});

	test.afterEach(async ({ apiClient }) => {
		try {
			await cleanupDeployments(apiClient, TEST_PREFIX);
			await cleanupFlowRuns(apiClient, TEST_PREFIX);
			await cleanupFlows(apiClient, TEST_PREFIX);
		} catch {
			// Ignore cleanup errors
		}
	});

	test("Navigate to deployment detail and view metadata", async ({
		page,
		apiClient,
	}) => {
		const timestamp = Date.now();
		const flowName = `${TEST_PREFIX}meta-flow-${timestamp}`;
		const depName = `${TEST_PREFIX}meta-dep-${timestamp}`;
		const flow = await createFlow(apiClient, flowName);
		const deployment = await createDeployment(apiClient, {
			name: depName,
			flowId: flow.id,
			tags: ["e2e-detail-tag"],
		});

		await page.goto(`/deployments/deployment/${deployment.id}`);

		await expect(page.getByText(depName)).toBeVisible({ timeout: 10000 });

		await expect(page.getByRole("link", { name: "Deployments" })).toBeVisible();

		await expect(page.getByText(flowName)).toBeVisible({ timeout: 10000 });

		await expect(page.getByRole("tab", { name: "Runs" })).toBeVisible();
		await expect(page.getByRole("tab", { name: "Upcoming" })).toBeVisible();
		await expect(page.getByRole("tab", { name: "Parameters" })).toBeVisible();

		await expect(page.getByText("e2e-detail-tag")).toBeVisible();
	});

	test("View flow runs in runs tab", async ({ page, apiClient }) => {
		const timestamp = Date.now();
		const flowName = `${TEST_PREFIX}runs-flow-${timestamp}`;
		const depName = `${TEST_PREFIX}runs-dep-${timestamp}`;
		const runName = `${TEST_PREFIX}runs-run-${timestamp}`;
		const flow = await createFlow(apiClient, flowName);
		const deployment = await createDeployment(apiClient, {
			name: depName,
			flowId: flow.id,
		});
		await createFlowRun(apiClient, {
			flowId: flow.id,
			name: runName,
			deploymentId: deployment.id,
			state: { type: "COMPLETED", name: "Completed" },
		});

		await page.goto(`/deployments/deployment/${deployment.id}`);

		await expect(page.getByText(depName)).toBeVisible({ timeout: 10000 });

		await expect(page.getByText(runName)).toBeVisible({ timeout: 10000 });
	});

	test("Quick run from deployment detail", async ({ page, apiClient }) => {
		const timestamp = Date.now();
		const flowName = `${TEST_PREFIX}quick-flow-${timestamp}`;
		const depName = `${TEST_PREFIX}quick-dep-${timestamp}`;
		const flow = await createFlow(apiClient, flowName);
		const deployment = await createDeployment(apiClient, {
			name: depName,
			flowId: flow.id,
		});

		await page.goto(`/deployments/deployment/${deployment.id}`);

		await expect(page.getByText(depName)).toBeVisible({ timeout: 10000 });

		await page.getByRole("button", { name: "Run" }).click();
		await page.getByRole("menuitem", { name: "Quick run" }).click();

		await expect(page.getByText("Flow run created")).toBeVisible({
			timeout: 10000,
		});

		await expect
			.poll(
				async () => {
					const runs = await listFlowRuns(apiClient);
					return runs.some(
						(r) =>
							r.deployment_id === deployment.id && r.state_type === "SCHEDULED",
					);
				},
				{ timeout: 10000 },
			)
			.toBe(true);
	});

	test("Edit page with pre-filled form and save", async ({
		page,
		apiClient,
	}) => {
		const timestamp = Date.now();
		const flowName = `${TEST_PREFIX}edit-flow-${timestamp}`;
		const depName = `${TEST_PREFIX}edit-dep-${timestamp}`;
		const flow = await createFlow(apiClient, flowName);
		const deployment = await createDeployment(apiClient, {
			name: depName,
			flowId: flow.id,
			tags: ["e2e-edit-tag"],
		});

		await page.goto(`/deployments/deployment/${deployment.id}/edit`);

		await expect(page.getByText("Edit")).toBeVisible({ timeout: 10000 });

		const form = page.locator("form");

		await expect(form.getByLabel("Name")).toHaveValue(depName);
		await expect(form.getByLabel("Name")).toBeDisabled();

		await form.getByRole("button", { name: "Save" }).click();

		await expect(page).toHaveURL(
			new RegExp(`/deployments/deployment/${deployment.id}`),
		);
		await expect(page.getByText("Deployment updated")).toBeVisible({
			timeout: 5000,
		});
	});

	test("Duplicate deployment with new name", async ({ page, apiClient }) => {
		const timestamp = Date.now();
		const flowName = `${TEST_PREFIX}dup-flow-${timestamp}`;
		const depName = `${TEST_PREFIX}dup-dep-${timestamp}`;
		const flow = await createFlow(apiClient, flowName);
		const deployment = await createDeployment(apiClient, {
			name: depName,
			flowId: flow.id,
		});

		await page.goto(`/deployments/deployment/${deployment.id}/duplicate`);

		await expect(page.getByText("Duplicate")).toBeVisible({ timeout: 10000 });

		const form = page.locator("form");

		await expect(form.getByLabel("Name")).toHaveValue(depName);
		await expect(form.getByLabel("Name")).not.toBeDisabled();

		const newName = `${TEST_PREFIX}dup-copy-${Date.now()}`;
		await form.getByLabel("Name").clear();
		await form.getByLabel("Name").fill(newName);

		await form.getByRole("button", { name: "Save" }).click();

		await expect(page).toHaveURL(/\/deployments\/deployment\//);
		await expect(page.getByText(newName)).toBeVisible({ timeout: 10000 });
		await expect(page.getByText("Deployment created")).toBeVisible({
			timeout: 5000,
		});
	});

	test("Delete deployment via action menu", async ({ page, apiClient }) => {
		const timestamp = Date.now();
		const flowName = `${TEST_PREFIX}del-flow-${timestamp}`;
		const depName = `${TEST_PREFIX}del-dep-${timestamp}`;
		const flow = await createFlow(apiClient, flowName);
		const deployment = await createDeployment(apiClient, {
			name: depName,
			flowId: flow.id,
		});

		await page.goto(`/deployments/deployment/${deployment.id}`);

		await expect(page.getByText(depName)).toBeVisible({ timeout: 10000 });

		const moreButton = page
			.getByRole("button")
			.filter({ has: page.locator(".lucide-ellipsis-vertical") });
		await moreButton.click();

		await page.getByRole("menuitem", { name: "Delete" }).click();

		await page
			.getByRole("alertdialog")
			.getByRole("button", { name: "Delete" })
			.click();

		await expect(page).toHaveURL(/\/deployments/, { timeout: 10000 });

		const deletedId = deployment.id;
		await expect
			.poll(
				async () => {
					const deps = await listDeployments(apiClient);
					return deps.some((d) => d.id === deletedId);
				},
				{ timeout: 10000 },
			)
			.toBe(false);
	});

	test("Schedule display on deployment detail", async ({ page, apiClient }) => {
		const timestamp = Date.now();
		const flowName = `${TEST_PREFIX}sched-flow-${timestamp}`;
		const depName = `${TEST_PREFIX}sched-dep-${timestamp}`;
		const flow = await createFlow(apiClient, flowName);
		const deployment = await createDeployment(apiClient, {
			name: depName,
			flowId: flow.id,
			schedules: [{ active: true, schedule: { interval: 300 } }],
		});

		await page.goto(`/deployments/deployment/${deployment.id}`);

		await expect(page.getByText(depName)).toBeVisible({ timeout: 10000 });

		await expect(page.getByText("Schedules")).toBeVisible();
		await expect(page.getByText("Every 5 minutes")).toBeVisible({
			timeout: 10000,
		});
	});
});
