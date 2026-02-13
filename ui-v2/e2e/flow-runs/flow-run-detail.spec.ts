import {
	cleanupFlowRuns,
	cleanupFlows,
	createDeployment,
	createFlow,
	createFlowRun,
	expect,
	runFlowWithTasks,
	runParentChild,
	test,
	waitForServerHealth,
} from "../fixtures";

const TEST_PREFIX = "e2e-frun-detail-";

test.describe("Flow Run Detail Page", () => {
	test.beforeAll(async ({ apiClient }) => {
		await waitForServerHealth(apiClient);
	});

	test.beforeEach(async ({ apiClient }) => {
		try {
			await cleanupFlows(apiClient, TEST_PREFIX);
			await cleanupFlowRuns(apiClient, TEST_PREFIX);
		} catch {
			// Ignore cleanup errors
		}
	});

	test.afterEach(async ({ apiClient }) => {
		try {
			await cleanupFlows(apiClient, TEST_PREFIX);
			await cleanupFlowRuns(apiClient, TEST_PREFIX);
		} catch {
			// Ignore cleanup errors
		}
	});

	test("FRUN-01: Navigate to flow run detail by ID", async ({
		page,
		apiClient,
	}) => {
		const flowName = `${TEST_PREFIX}nav-${Date.now()}`;
		const flow = await createFlow(apiClient, flowName);
		const runName = `${TEST_PREFIX}nav-run-${Date.now()}`;
		const flowRun = await createFlowRun(apiClient, {
			flowId: flow.id,
			name: runName,
			state: { type: "COMPLETED", name: "Completed" },
		});

		await page.goto(`/runs/flow-run/${flowRun.id}`);

		await expect(page.getByText(runName)).toBeVisible({ timeout: 10000 });
		await expect(page).toHaveURL(new RegExp(`/runs/flow-run/${flowRun.id}`));
		await expect(page.getByRole("tab", { name: "Logs" })).toBeVisible();
		await expect(page.getByRole("tab", { name: "Details" })).toBeVisible();
		await expect(page.getByRole("tab", { name: "Artifacts" })).toBeVisible();
		await expect(page.getByRole("tab", { name: "Parameters" })).toBeVisible();
	});

	test("FRUN-02: Flow run metadata display", async ({ page, apiClient }) => {
		const flowName = `${TEST_PREFIX}meta-${Date.now()}`;
		const flow = await createFlow(apiClient, flowName);
		const runName = `${TEST_PREFIX}meta-run-${Date.now()}`;
		const flowRun = await createFlowRun(apiClient, {
			flowId: flow.id,
			name: runName,
			state: { type: "COMPLETED", name: "Completed" },
		});

		await page.goto(`/runs/flow-run/${flowRun.id}`);

		await expect(page.getByText(runName)).toBeVisible({ timeout: 10000 });

		const header = page.locator(".flex.flex-col.gap-2").first();
		await expect(header.locator('[class*="bg-state-completed"]')).toBeVisible();
		await expect(header.getByText("Completed")).toBeVisible();
	});

	test("FRUN-02b: Deployment link shows for deployment-linked run", async ({
		page,
		apiClient,
	}) => {
		const flowName = `${TEST_PREFIX}deploy-${Date.now()}`;
		const flow = await createFlow(apiClient, flowName);

		const deploymentName = `${TEST_PREFIX}dep-${Date.now()}`;
		const deployment = await createDeployment(apiClient, {
			name: deploymentName,
			flowId: flow.id,
		});

		const runName = `${TEST_PREFIX}deploy-run-${Date.now()}`;
		const flowRun = await createFlowRun(apiClient, {
			flowId: flow.id,
			deploymentId: deployment.id,
			name: runName,
			state: { type: "COMPLETED", name: "Completed" },
		});

		await page.goto(`/runs/flow-run/${flowRun.id}`);
		await expect(page.getByText(runName)).toBeVisible({ timeout: 10000 });
		await expect(page.getByText(deploymentName)).toBeVisible();

		const adhocRunName = `${TEST_PREFIX}adhoc-run-${Date.now()}`;
		const adhocRun = await createFlowRun(apiClient, {
			flowId: flow.id,
			name: adhocRunName,
			state: { type: "COMPLETED", name: "Completed" },
		});

		await page.goto(`/runs/flow-run/${adhocRun.id}`);
		await expect(page.getByText(adhocRunName)).toBeVisible({
			timeout: 10000,
		});
		await expect(page.getByText("Deployment")).not.toBeVisible();
	});

	test("FRUN-07: State badge colors for 5 states", async ({
		page,
		apiClient,
	}) => {
		const flowName = `${TEST_PREFIX}states-${Date.now()}`;
		const flow = await createFlow(apiClient, flowName);

		const states = [
			{
				type: "COMPLETED" as const,
				name: "Completed",
				cssClass: "bg-state-completed",
			},
			{
				type: "FAILED" as const,
				name: "Failed",
				cssClass: "bg-state-failed",
			},
			{
				type: "RUNNING" as const,
				name: "Running",
				cssClass: "bg-state-running",
			},
			{
				type: "CANCELLED" as const,
				name: "Cancelled",
				cssClass: "bg-state-cancelled",
			},
			{
				type: "PENDING" as const,
				name: "Pending",
				cssClass: "bg-state-pending",
			},
		];

		const runs = [];
		for (const state of states) {
			const runName = `${TEST_PREFIX}state-${state.type.toLowerCase()}-${Date.now()}`;
			const flowRun = await createFlowRun(apiClient, {
				flowId: flow.id,
				name: runName,
				state: { type: state.type, name: state.name },
			});
			runs.push({ ...state, runName, flowRun });
		}

		for (const run of runs) {
			await page.goto(`/runs/flow-run/${run.flowRun.id}`);
			await expect(page.getByText(run.runName)).toBeVisible({
				timeout: 10000,
			});

			const header = page.locator(".flex.flex-col.gap-2").first();
			await expect(header.locator(`[class*="${run.cssClass}"]`)).toBeVisible();
			await expect(
				header.locator(`[class*="${run.cssClass}"]`).getByText(run.name),
			).toBeVisible();
		}
	});

	test("FRUN-08: Parent-child related runs", async ({ page }) => {
		const result = runParentChild(TEST_PREFIX);

		await page.goto(`/runs/flow-run/${result.child_flow_run_id}`);
		await expect(page.getByText(result.child_flow_run_name)).toBeVisible({
			timeout: 15000,
		});

		await expect(page.getByText("Parent Run")).toBeVisible({
			timeout: 10000,
		});

		const parentLink = page
			.getByRole("link")
			.filter({ hasText: result.parent_flow_run_name });
		await expect(parentLink).toBeVisible({ timeout: 10000 });
		await parentLink.click();

		await expect(page).toHaveURL(
			new RegExp(`/runs/flow-run/${result.parent_flow_run_id}`),
		);
		await expect(page.getByText(result.parent_flow_run_name)).toBeVisible({
			timeout: 10000,
		});
	});

	test("FRUN-09: Flow run graph renders canvas for run with tasks", async ({
		page,
		apiClient,
	}) => {
		const result = runFlowWithTasks(TEST_PREFIX);

		await page.goto(`/runs/flow-run/${result.flow_run_id}`);
		await expect(page.getByText(result.flow_run_name)).toBeVisible({
			timeout: 15000,
		});

		await expect(page.locator("canvas")).toBeVisible({ timeout: 15000 });

		const flowName = `${TEST_PREFIX}empty-graph-${Date.now()}`;
		const flow = await createFlow(apiClient, flowName);
		const emptyRunName = `${TEST_PREFIX}empty-run-${Date.now()}`;
		const emptyRun = await createFlowRun(apiClient, {
			flowId: flow.id,
			name: emptyRunName,
			state: { type: "COMPLETED", name: "Completed" },
		});

		await page.goto(`/runs/flow-run/${emptyRun.id}`);
		await expect(page.getByText(emptyRunName)).toBeVisible({
			timeout: 10000,
		});

		await expect(
			page.getByText("did not generate any task or subflow runs"),
		).toBeVisible({ timeout: 10000 });

		const pendingRunName = `${TEST_PREFIX}pending-run-${Date.now()}`;
		const pendingRun = await createFlowRun(apiClient, {
			flowId: flow.id,
			name: pendingRunName,
			state: { type: "PENDING", name: "Pending" },
		});

		await page.goto(`/runs/flow-run/${pendingRun.id}`);
		await expect(page.getByText(pendingRunName)).toBeVisible({
			timeout: 10000,
		});

		await expect(page.locator("canvas")).not.toBeVisible({ timeout: 5000 });
	});
});
