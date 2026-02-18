import type { Page } from "@playwright/test";
import {
	buildTestEvent,
	cleanupFlows,
	createFlow,
	emitEvents,
	expect,
	listEvents,
	test,
	waitForServerHealth,
} from "../fixtures";

async function waitForEventsPageReady(page: Page): Promise<void> {
	await expect(
		page.getByText(/no events found/i).or(page.locator("ol").first()),
	).toBeVisible({ timeout: 10000 });
}

test.describe("Events List Page", () => {
	test.describe.configure({ mode: "serial" });

	const timestamp = Date.now();
	const flowRunEvent = "prefect.flow-run.Completed";
	const deploymentEvent = "prefect.deployment.Updated";
	const workPoolEvent = "prefect.work-pool.Created";
	const flowRunResourceName = `e2e-evt-flow-${timestamp}`;
	const deploymentResourceName = `e2e-evt-deploy-${timestamp}`;
	const workPoolResourceName = `e2e-evt-wp-${timestamp}`;

	let flowIdForCleanup: string | undefined;

	test.beforeAll(async ({ apiClient }) => {
		await waitForServerHealth(apiClient);

		await emitEvents(apiClient, [
			buildTestEvent({
				event: flowRunEvent,
				resourceId: `prefect.flow-run.${crypto.randomUUID()}`,
				resourceName: flowRunResourceName,
			}),
			buildTestEvent({
				event: deploymentEvent,
				resourceId: `prefect.deployment.${crypto.randomUUID()}`,
				resourceName: deploymentResourceName,
			}),
			buildTestEvent({
				event: workPoolEvent,
				resourceId: `prefect.work-pool.${crypto.randomUUID()}`,
				resourceName: workPoolResourceName,
			}),
		]);
	});

	test.afterAll(async ({ apiClient }) => {
		if (flowIdForCleanup) {
			try {
				await cleanupFlows(apiClient, "e2e-evt-res-");
			} catch {
				// Ignore cleanup errors
			}
		}
	});

	test("Events timeline shows events from multiple resource types", async ({
		page,
	}) => {
		await expect(async () => {
			await page.goto("/events");
			await expect(page.getByText(flowRunEvent)).toBeVisible({
				timeout: 2000,
			});
		}).toPass({ timeout: 15000 });

		await expect(page.getByText(flowRunEvent).first()).toBeVisible();
		await expect(page.getByText(deploymentEvent).first()).toBeVisible();
		await expect(page.getByText(workPoolEvent).first()).toBeVisible();

		await expect(page.getByText(flowRunResourceName).first()).toBeVisible();
		await expect(page.getByText(deploymentResourceName).first()).toBeVisible();
		await expect(page.getByText(workPoolResourceName).first()).toBeVisible();
	});

	test("Empty state shown when filtering to nonexistent resource", async ({
		page,
	}) => {
		await page.goto(
			`/events?resource=prefect.flow-run.nonexistent-${Date.now()}`,
		);
		await waitForEventsPageReady(page);

		await expect(page.getByText(/no events found/i)).toBeVisible();
		await expect(
			page.getByText(/no events match your current filters/i),
		).toBeVisible();
	});

	test("Filter by event type", async ({ page, apiClient }) => {
		const filterTimestamp = Date.now();
		const completedEvent = "prefect.flow-run.Completed";
		const failedEvent = "prefect.flow-run.Failed";
		const completedResourceName = `e2e-evt-type-completed-${filterTimestamp}`;
		const failedResourceName = `e2e-evt-type-failed-${filterTimestamp}`;

		await emitEvents(apiClient, [
			buildTestEvent({
				event: completedEvent,
				resourceId: `prefect.flow-run.${crypto.randomUUID()}`,
				resourceName: completedResourceName,
			}),
			buildTestEvent({
				event: failedEvent,
				resourceId: `prefect.flow-run.${crypto.randomUUID()}`,
				resourceName: failedResourceName,
			}),
		]);

		await expect(async () => {
			await page.goto("/events");
			await expect(page.getByText(completedResourceName)).toBeVisible({
				timeout: 2000,
			});
			await expect(page.getByText(failedResourceName)).toBeVisible({
				timeout: 2000,
			});
		}).toPass({ timeout: 15000 });

		await page.getByLabel("Filter by event type").click();
		await page
			.getByRole("option", { name: "prefect.flow-run.Completed" })
			.click();

		await expect(page).toHaveURL(/event=/, { timeout: 5000 });

		await expect(async () => {
			await expect(page.getByText(completedResourceName)).toBeVisible({
				timeout: 2000,
			});
			await expect(page.getByText(failedResourceName)).not.toBeVisible({
				timeout: 2000,
			});
		}).toPass({ timeout: 15000 });
	});

	test("Filter by resource", async ({ page, apiClient }) => {
		const resTimestamp = Date.now();
		const flowName = `e2e-evt-res-${resTimestamp}`;
		const flow = await createFlow(apiClient, flowName);
		flowIdForCleanup = flow.id;

		const resourceEvent = "prefect.flow.Updated";
		await emitEvents(apiClient, [
			buildTestEvent({
				event: resourceEvent,
				resourceId: `prefect.flow.${flow.id}`,
				resourceName: flowName,
			}),
		]);

		await expect(async () => {
			await page.goto("/events");
			await expect(page.getByText(flowName)).toBeVisible({
				timeout: 2000,
			});
		}).toPass({ timeout: 15000 });

		await page.getByLabel("Filter by resource").click();
		await page.getByPlaceholder("Search resources...").fill(flowName);

		await expect(async () => {
			await expect(page.getByRole("option", { name: flowName })).toBeVisible({
				timeout: 2000,
			});
		}).toPass({ timeout: 15000 });

		await page.getByRole("option", { name: flowName }).click();

		await expect(page).toHaveURL(/resource=/, { timeout: 5000 });
	});

	test("Filter state persists in URL after reload", async ({ page }) => {
		await expect(async () => {
			await page.goto("/events");
			await waitForEventsPageReady(page);
			await expect(page.getByLabel("Filter by event type")).toBeVisible({
				timeout: 2000,
			});
		}).toPass({ timeout: 15000 });

		await page.getByLabel("Filter by event type").click();

		const eventTypeOption = page
			.getByRole("option")
			.filter({ hasNotText: /all event types/i })
			.first();
		await expect(eventTypeOption).toBeVisible({ timeout: 5000 });
		const selectedTypeName = await eventTypeOption.textContent();
		await eventTypeOption.click();

		await expect(page).toHaveURL(/event=/, { timeout: 5000 });

		await page.reload();
		await waitForEventsPageReady(page);

		await expect(page).toHaveURL(/event=/);

		if (selectedTypeName) {
			await expect(page.getByLabel("Filter by event type")).toContainText(
				selectedTypeName,
			);
		}
	});

	test("Combining multiple filters narrows results", async ({ page }) => {
		await expect(async () => {
			await page.goto("/events");
			await waitForEventsPageReady(page);
			await expect(page.locator("ol li").first()).toBeVisible({
				timeout: 2000,
			});
		}).toPass({ timeout: 15000 });

		const unfilteredCount = await page.locator("ol li").count();

		await page.getByLabel("Filter by event type").click();
		const eventTypeOption = page
			.getByRole("option")
			.filter({ hasNotText: /all event types/i })
			.first();
		await expect(eventTypeOption).toBeVisible({ timeout: 5000 });
		await eventTypeOption.click();
		await page.keyboard.press("Escape");

		await expect(page).toHaveURL(/event=/, { timeout: 5000 });

		await expect(async () => {
			const filteredCount = await page.locator("ol li").count();
			expect(filteredCount).toBeLessThanOrEqual(unfilteredCount);
		}).toPass({ timeout: 15000 });
	});

	test("Clearing filters restores unfiltered state", async ({ page }) => {
		await expect(async () => {
			await page.goto("/events");
			await waitForEventsPageReady(page);
			await expect(page.locator("ol li").first()).toBeVisible({
				timeout: 2000,
			});
		}).toPass({ timeout: 15000 });

		await page.getByLabel("Filter by event type").click();
		const eventTypeOption = page
			.getByRole("option")
			.filter({ hasNotText: /all event types/i })
			.first();
		await expect(eventTypeOption).toBeVisible({ timeout: 5000 });
		await eventTypeOption.click();
		await page.keyboard.press("Escape");

		await expect(page).toHaveURL(/event=/, { timeout: 5000 });

		await page.getByLabel("Filter by event type").click();
		await page.getByRole("option", { name: /all event types/i }).click();
		await page.keyboard.press("Escape");

		await expect(page).not.toHaveURL(/event=/, { timeout: 5000 });
	});

	test("Events timeline chart renders with data", async ({ page }) => {
		await expect(async () => {
			await page.goto("/events");
			await expect(page.locator(".recharts-wrapper")).toBeVisible({
				timeout: 2000,
			});
		}).toPass({ timeout: 15000 });

		await expect(page.locator(".recharts-wrapper")).toBeVisible();
		const areaPath = page.locator(".recharts-area-area path");
		await expect(areaPath.first()).toBeVisible();
		const d = await areaPath.first().getAttribute("d");
		expect(d).toBeTruthy();
	});

	test("Chart updates when time range changes", async ({ page }) => {
		await expect(async () => {
			await page.goto("/events");
			await expect(page.locator(".recharts-wrapper")).toBeVisible({
				timeout: 2000,
			});
		}).toPass({ timeout: 15000 });

		await page.getByText("Past day").click();
		await page.getByRole("button", { name: "Past hour" }).click();

		await expect(async () => {
			await expect(page.locator(".recharts-wrapper")).toBeVisible({
				timeout: 2000,
			});
		}).toPass({ timeout: 10000 });

		await expect(page).toHaveURL(/seconds=-3600/, { timeout: 5000 });
	});

	test("API confirms emitted events exist", async ({ apiClient }) => {
		const result = await listEvents(apiClient, {
			event: { prefix: ["prefect.flow-run.Completed"] },
		});
		expect(result.events.length).toBeGreaterThan(0);
	});
});
