import type { Page } from "@playwright/test";
import {
	buildTestEvent,
	cleanupFlowRuns,
	cleanupFlows,
	createFlow,
	createFlowRun,
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

const DETAIL_PREFIX = "e2e-evt-detail-";

test.describe("Event Detail", () => {
	test.describe.configure({ mode: "serial", timeout: 120_000 });

	const detailTimestamp = Date.now();
	const detailResourceName = `${DETAIL_PREFIX}${detailTimestamp}`;
	let detailEventId: string;
	let detailFlowRunId: string;
	let detailEventOccurred: string;

	test.beforeAll(async ({ apiClient }) => {
		await waitForServerHealth(apiClient);

		// Retry setup to handle transient 503s during server warm-up
		let flow: Awaited<ReturnType<typeof createFlow>>;
		let flowRun: Awaited<ReturnType<typeof createFlowRun>>;
		const setupDeadline = Date.now() + 30_000;
		while (Date.now() < setupDeadline) {
			try {
				flow = await createFlow(
					apiClient,
					`${DETAIL_PREFIX}flow-${detailTimestamp}`,
				);
				flowRun = await createFlowRun(apiClient, {
					flowId: flow.id,
					name: `${DETAIL_PREFIX}run-${detailTimestamp}`,
					state: { type: "COMPLETED", name: "Completed" },
				});
				break;
			} catch {
				await new Promise((r) => setTimeout(r, 2000));
			}
		}
		if (!flowRun) {
			throw new Error("Failed to create flow/flow-run after 30s of retries");
		}
		detailFlowRunId = flowRun.id;

		const testEvent = buildTestEvent({
			event: "prefect.flow-run.Completed",
			resourceId: `prefect.flow-run.${flowRun.id}`,
			resourceName: detailResourceName,
			payload: { duration: 42, status: "success" },
		});
		detailEventId = testEvent.id;
		detailEventOccurred = testEvent.occurred;

		await emitEvents(apiClient, [testEvent]);

		const deadline = Date.now() + 45_000;
		let indexed = false;
		while (Date.now() < deadline && !indexed) {
			const result = await listEvents(apiClient, {
				any_resource: {
					id_prefix: [`prefect.flow-run.${flowRun.id}`],
				},
			});
			const found = result.events.some((e) => e.id === detailEventId);
			if (found) {
				indexed = true;
			} else {
				await new Promise((r) => setTimeout(r, 2000));
			}
		}
		if (!indexed) {
			throw new Error(`Event not indexed within 45s: ${detailEventId}`);
		}
	});

	test.afterAll(async ({ apiClient }) => {
		try {
			await cleanupFlowRuns(apiClient, DETAIL_PREFIX);
		} catch {
			/* ignore */
		}
		try {
			await cleanupFlows(apiClient, DETAIL_PREFIX);
		} catch {
			/* ignore */
		}
	});

	test("Navigate to event detail from events list", async ({ page }) => {
		await expect(async () => {
			await page.goto("/events");
			await expect(page.getByText(detailResourceName).first()).toBeVisible({
				timeout: 2000,
			});
		}).toPass({ timeout: 60_000 });

		// Scope click to the specific list item containing our unique resource name
		const eventItem = page
			.getByRole("listitem")
			.filter({ hasText: detailResourceName });
		await eventItem.getByRole("link", { name: /flow run completed/i }).click();

		await expect(page).toHaveURL(
			new RegExp(`/events/event/\\d{4}-\\d{2}-\\d{2}/${detailEventId}`),
			{ timeout: 10000 },
		);

		await expect(
			page.getByLabel("breadcrumb").getByText("Flow Run Completed"),
		).toBeVisible({ timeout: 10000 });
	});

	test("Navigate to event detail via direct URL deep link", async ({
		page,
	}) => {
		const eventDate = new Date(detailEventOccurred);
		const dateStr = `${eventDate.getFullYear()}-${String(eventDate.getMonth() + 1).padStart(2, "0")}-${String(eventDate.getDate()).padStart(2, "0")}`;

		await page.goto(`/events/event/${dateStr}/${detailEventId}`);

		await expect(
			page.getByLabel("breadcrumb").getByText("Flow Run Completed"),
		).toBeVisible({ timeout: 10000 });

		await expect(page.getByText("prefect.flow-run.Completed")).toBeVisible();
	});

	test("Event detail page shows metadata on Details tab", async ({ page }) => {
		const eventDate = new Date(detailEventOccurred);
		const dateStr = `${eventDate.getFullYear()}-${String(eventDate.getMonth() + 1).padStart(2, "0")}-${String(eventDate.getDate()).padStart(2, "0")}`;
		await page.goto(`/events/event/${dateStr}/${detailEventId}`);

		await expect(
			page.getByLabel("breadcrumb").getByText("Flow Run Completed"),
		).toBeVisible({ timeout: 10000 });

		await expect(page.getByRole("tab", { name: "Details" })).toBeVisible();

		await expect(page.getByText("prefect.flow-run.Completed")).toBeVisible();

		await expect(page.getByText(detailResourceName)).toBeVisible();

		await expect(page.getByText("Occurred")).toBeVisible();
	});

	test("Event detail page shows raw JSON payload on Raw tab", async ({
		page,
	}) => {
		const eventDate = new Date(detailEventOccurred);
		const dateStr = `${eventDate.getFullYear()}-${String(eventDate.getMonth() + 1).padStart(2, "0")}-${String(eventDate.getDate()).padStart(2, "0")}`;
		await page.goto(`/events/event/${dateStr}/${detailEventId}`);

		await expect(
			page.getByLabel("breadcrumb").getByText("Flow Run Completed"),
		).toBeVisible({ timeout: 10000 });

		await page.getByRole("tab", { name: "Raw" }).click();

		await expect(page.getByText('"duration"')).toBeVisible({
			timeout: 5000,
		});
		await expect(page.getByText('"status"')).toBeVisible();

		await expect(page.getByText(detailEventId)).toBeVisible();
	});

	test("Resource link navigates to flow run detail page", async ({ page }) => {
		const eventDate = new Date(detailEventOccurred);
		const dateStr = `${eventDate.getFullYear()}-${String(eventDate.getMonth() + 1).padStart(2, "0")}-${String(eventDate.getDate()).padStart(2, "0")}`;
		await page.goto(`/events/event/${dateStr}/${detailEventId}`);

		await expect(
			page.getByLabel("breadcrumb").getByText("Flow Run Completed"),
		).toBeVisible({ timeout: 10000 });

		await expect(page.getByRole("tab", { name: "Details" })).toBeVisible();

		await page
			.getByRole("link", { name: new RegExp(detailResourceName) })
			.click();

		await expect(page).toHaveURL(
			new RegExp(`/runs/flow-run/${detailFlowRunId}`),
			{ timeout: 10000 },
		);

		await expect(page.getByLabel("breadcrumb")).toBeVisible({
			timeout: 10000,
		});
	});
});
