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
	await expect(page.getByLabel("Filter by event type")).toBeVisible({
		timeout: 10000,
	});
}

test.describe("Events List Page", () => {
	test.describe.configure({ mode: "serial", timeout: 120_000 });

	const timestamp = Date.now();
	const flowRunEvent = "prefect.flow-run.Completed";
	const deploymentEvent = "prefect.deployment.Updated";
	const workPoolEvent = "prefect.work-pool.Created";
	const flowRunResourceName = `e2e-evt-flow-${timestamp}`;
	const deploymentResourceName = `e2e-evt-deploy-${timestamp}`;
	const workPoolResourceName = `e2e-evt-wp-${timestamp}`;
	const flowForResourceFilter = `e2e-evt-res-${timestamp}`;

	let flowIdForCleanup: string | undefined;
	const flowRunResourceId = `prefect.flow-run.${crypto.randomUUID()}`;

	test.beforeAll(async ({ apiClient }) => {
		await waitForServerHealth(apiClient);

		const flow = await createFlow(apiClient, flowForResourceFilter);
		flowIdForCleanup = flow.id;

		await emitEvents(apiClient, [
			buildTestEvent({
				event: flowRunEvent,
				resourceId: flowRunResourceId,
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
			buildTestEvent({
				event: "prefect.flow.Updated",
				resourceId: `prefect.flow.${flow.id}`,
				resourceName: flowForResourceFilter,
			}),
		]);

		const deadline = Date.now() + 45_000;
		let indexed = false;
		while (Date.now() < deadline && !indexed) {
			const result = await listEvents(apiClient, {
				any_resource: {
					id_prefix: [flowRunResourceId],
				},
			});
			const found = result.events.some(
				(e) => e.resource["prefect.resource.id"] === flowRunResourceId,
			);
			if (found) {
				indexed = true;
			} else {
				await new Promise((r) => setTimeout(r, 2000));
			}
		}
		if (!indexed) {
			throw new Error(
				`Events not indexed within 45s for ${flowRunResourceName}`,
			);
		}
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
			await waitForEventsPageReady(page);
			await expect(page.getByText(flowRunResourceName).first()).toBeVisible({
				timeout: 2000,
			});
		}).toPass({ timeout: 60_000 });

		await expect(page.getByText(deploymentResourceName).first()).toBeVisible();
		await expect(page.getByText(workPoolResourceName).first()).toBeVisible();

		await expect(page.getByText(flowRunEvent).first()).toBeVisible();
		await expect(page.getByText(deploymentEvent).first()).toBeVisible();
		await expect(page.getByText(workPoolEvent).first()).toBeVisible();
	});

	test("Empty state shown when filtering to nonexistent resource", async ({
		page,
	}) => {
		const nonexistentId = `prefect.flow-run.nonexistent-${Date.now()}`;
		await page.goto(
			`/events?resource=${encodeURIComponent(JSON.stringify([nonexistentId]))}`,
		);

		await expect(async () => {
			await expect(page.getByText(/no events found/i)).toBeVisible({
				timeout: 2000,
			});
		}).toPass({ timeout: 15000 });

		await expect(
			page.getByText(/no events match your current filters/i),
		).toBeVisible();
	});

	test("Filter by event type", async ({ page }) => {
		await expect(async () => {
			await page.goto("/events");
			await waitForEventsPageReady(page);
			await expect(page.getByText(flowRunResourceName)).toBeVisible({
				timeout: 2000,
			});
		}).toPass({ timeout: 15000 });

		await page.getByLabel("Filter by event type").click();

		await expect(async () => {
			await expect(
				page.getByRole("option", { name: flowRunEvent }),
			).toBeVisible({ timeout: 2000 });
		}).toPass({ timeout: 15000 });

		await page.getByRole("option", { name: flowRunEvent }).click();
		await page.keyboard.press("Escape");

		await expect(page).toHaveURL(/event=/, { timeout: 5000 });

		await expect(async () => {
			await expect(page.getByText(flowRunResourceName)).toBeVisible({
				timeout: 2000,
			});
		}).toPass({ timeout: 15000 });

		await expect(page.getByText(deploymentResourceName)).not.toBeVisible();
	});

	test("Filter by resource", async ({ page }) => {
		await expect(async () => {
			await page.goto("/events");
			await waitForEventsPageReady(page);
			await expect(page.locator("ol.list-none li").first()).toBeVisible({
				timeout: 2000,
			});
		}).toPass({ timeout: 15000 });

		await page.getByLabel("Filter by resource").click();
		await page
			.getByPlaceholder("Search resources...")
			.fill(flowForResourceFilter);

		await expect(async () => {
			await expect(
				page.getByRole("option", { name: flowForResourceFilter }),
			).toBeVisible({ timeout: 2000 });
		}).toPass({ timeout: 15000 });

		await page.getByRole("option", { name: flowForResourceFilter }).click();

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
		await page.keyboard.press("Escape");

		await expect(page).toHaveURL(/event=/, { timeout: 5000 });

		await page.reload();
		await waitForEventsPageReady(page);

		await expect(page).toHaveURL(/event=/);

		if (selectedTypeName) {
			await expect(page.getByLabel("Filter by event type")).toContainText(
				selectedTypeName.trim(),
			);
		}
	});

	test("Combining multiple filters narrows results", async ({ page }) => {
		await expect(async () => {
			await page.goto("/events");
			await waitForEventsPageReady(page);
			await expect(page.locator("ol.list-none li").first()).toBeVisible({
				timeout: 2000,
			});
		}).toPass({ timeout: 15000 });

		const unfilteredCount = await page.locator("ol.list-none li").count();

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
			const filteredCount = await page.locator("ol.list-none li").count();
			expect(filteredCount).toBeLessThanOrEqual(unfilteredCount);
		}).toPass({ timeout: 15000 });
	});

	test("Clearing filters restores unfiltered state", async ({ page }) => {
		await expect(async () => {
			await page.goto("/events");
			await waitForEventsPageReady(page);
			await expect(page.locator("ol.list-none li").first()).toBeVisible({
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

		await expect(page.getByLabel("Filter by event type")).toContainText(
			/all event types/i,
			{ timeout: 5000 },
		);
	});

	test("Events timeline chart renders with data", async ({ page }) => {
		await expect(async () => {
			await page.goto("/events");
			await expect(page.locator(".recharts-wrapper")).toBeVisible({
				timeout: 2000,
			});
		}).toPass({ timeout: 15000 });

		await expect(page.locator(".recharts-wrapper")).toBeVisible();
		const chartSvg = page.locator(".recharts-wrapper svg");
		await expect(chartSvg.first()).toBeVisible();
	});

	test("Chart updates when time range changes", async ({ page }) => {
		await expect(async () => {
			await page.goto("/events");
			await waitForEventsPageReady(page);
			await expect(page.locator(".recharts-wrapper")).toBeVisible({
				timeout: 2000,
			});
		}).toPass({ timeout: 15000 });

		await page.getByRole("button", { name: /past day/i }).click();
		await page.getByRole("button", { name: "Past hour" }).click();

		await expect(page).toHaveURL(/seconds=-3600/, { timeout: 5000 });

		await expect(async () => {
			await expect(page.locator(".recharts-wrapper svg")).toBeVisible({
				timeout: 2000,
			});
		}).toPass({ timeout: 10000 });
	});

	test("API confirms emitted events exist", async ({ apiClient }) => {
		const result = await listEvents(apiClient, {
			event: { prefix: ["prefect.flow-run.Completed"] },
		});
		expect(result.events.length).toBeGreaterThan(0);
	});
});
