import { describe, expect, it } from "vitest";
import { createFakeEvent } from "@/mocks";
import {
	formatEventDate,
	getPrefectResourceRole,
	transformEventToTrigger,
} from "./event-to-trigger";

describe("getPrefectResourceRole", () => {
	it("extracts flow-run role from event type", () => {
		expect(getPrefectResourceRole("prefect.flow-run.Completed")).toBe(
			"flow-run",
		);
		expect(getPrefectResourceRole("prefect.flow-run.Running")).toBe("flow-run");
		expect(getPrefectResourceRole("prefect.flow-run.Failed")).toBe("flow-run");
	});

	it("extracts work-queue role from event type", () => {
		expect(getPrefectResourceRole("prefect.work-queue.ready")).toBe(
			"work-queue",
		);
		expect(getPrefectResourceRole("prefect.work-queue.not-ready")).toBe(
			"work-queue",
		);
	});

	it("extracts deployment role from event type", () => {
		expect(getPrefectResourceRole("prefect.deployment.created")).toBe(
			"deployment",
		);
		expect(getPrefectResourceRole("prefect.deployment.updated")).toBe(
			"deployment",
		);
	});

	it("extracts flow role from event type", () => {
		expect(getPrefectResourceRole("prefect.flow.created")).toBe("flow");
	});

	it("extracts work-pool role from event type", () => {
		expect(getPrefectResourceRole("prefect.work-pool.ready")).toBe("work-pool");
	});

	it("extracts task-run role from event type", () => {
		expect(getPrefectResourceRole("prefect.task-run.Completed")).toBe(
			"task-run",
		);
	});

	it("extracts automation role from event type", () => {
		expect(getPrefectResourceRole("prefect.automation.triggered")).toBe(
			"automation",
		);
	});

	it("returns null for custom/unknown event types", () => {
		expect(getPrefectResourceRole("custom.event.type")).toBeNull();
		expect(getPrefectResourceRole("my-app.user.created")).toBeNull();
		expect(getPrefectResourceRole("unknown")).toBeNull();
	});

	it("returns null for empty string", () => {
		expect(getPrefectResourceRole("")).toBeNull();
	});
});

describe("transformEventToTrigger", () => {
	describe("flow-run events", () => {
		it("creates trigger with match_related for flow-run event with related flow", () => {
			const event = createFakeEvent({
				event: "prefect.flow-run.Completed",
				resource: {
					"prefect.resource.id": "prefect.flow-run.abc123",
					"prefect.resource.name": "my-flow-run",
				},
				related: [
					{
						"prefect.resource.role": "flow",
						"prefect.resource.id": "prefect.flow.xyz789",
					},
				],
			});

			const result = transformEventToTrigger(event);

			expect(result.triggerTemplate).toBe("custom");
			expect(result.trigger).toEqual({
				type: "event",
				match: {
					"prefect.resource.id": "prefect.flow-run.abc123",
				},
				match_related: {
					"prefect.resource.role": "flow",
					"prefect.resource.id": "prefect.flow.xyz789",
				},
				after: [],
				expect: ["prefect.flow-run.Completed"],
				for_each: ["prefect.resource.id"],
				posture: "Reactive",
				threshold: 1,
				within: 0,
			});
		});

		it("creates trigger without match_related for flow-run event without related flow", () => {
			const event = createFakeEvent({
				event: "prefect.flow-run.Running",
				resource: {
					"prefect.resource.id": "prefect.flow-run.abc123",
				},
				related: [],
			});

			const result = transformEventToTrigger(event);

			expect(result.triggerTemplate).toBe("custom");
			expect(result.trigger).toEqual({
				type: "event",
				match: {
					"prefect.resource.id": "prefect.flow-run.abc123",
				},
				match_related: {},
				after: [],
				expect: ["prefect.flow-run.Running"],
				for_each: ["prefect.resource.id"],
				posture: "Reactive",
				threshold: 1,
				within: 0,
			});
		});

		it("handles flow-run event with multiple related resources", () => {
			const event = createFakeEvent({
				event: "prefect.flow-run.Failed",
				resource: {
					"prefect.resource.id": "prefect.flow-run.abc123",
				},
				related: [
					{
						"prefect.resource.role": "deployment",
						"prefect.resource.id": "prefect.deployment.dep123",
					},
					{
						"prefect.resource.role": "flow",
						"prefect.resource.id": "prefect.flow.flow456",
					},
					{
						"prefect.resource.role": "work-pool",
						"prefect.resource.id": "prefect.work-pool.pool789",
					},
				],
			});

			const result = transformEventToTrigger(event);

			expect(result.trigger.match_related).toEqual({
				"prefect.resource.role": "flow",
				"prefect.resource.id": "prefect.flow.flow456",
			});
		});
	});

	describe("work-queue events", () => {
		it("creates trigger with match_related for work-queue event with related work-queue", () => {
			const event = createFakeEvent({
				event: "prefect.work-queue.ready",
				resource: {
					"prefect.resource.id": "prefect.work-queue.queue123",
				},
				related: [
					{
						"prefect.resource.role": "work-queue",
						"prefect.resource.id": "prefect.work-queue.related456",
					},
				],
			});

			const result = transformEventToTrigger(event);

			expect(result.triggerTemplate).toBe("custom");
			expect(result.trigger).toEqual({
				type: "event",
				match: {
					"prefect.resource.id": "prefect.work-queue.queue123",
				},
				match_related: {
					"prefect.resource.role": "work-queue",
					"prefect.resource.id": "prefect.work-queue.related456",
				},
				after: [],
				expect: ["prefect.work-queue.ready"],
				for_each: ["prefect.resource.id"],
				posture: "Reactive",
				threshold: 1,
				within: 0,
			});
		});

		it("creates trigger without match_related for work-queue event without related work-queue", () => {
			const event = createFakeEvent({
				event: "prefect.work-queue.not-ready",
				resource: {
					"prefect.resource.id": "prefect.work-queue.queue123",
				},
				related: [],
			});

			const result = transformEventToTrigger(event);

			expect(result.trigger.match_related).toEqual({});
			expect(result.trigger.expect).toEqual(["prefect.work-queue.not-ready"]);
		});
	});

	describe("deployment events", () => {
		it("creates basic custom trigger for deployment events", () => {
			const event = createFakeEvent({
				event: "prefect.deployment.created",
				resource: {
					"prefect.resource.id": "prefect.deployment.dep123",
				},
				related: [
					{
						"prefect.resource.role": "flow",
						"prefect.resource.id": "prefect.flow.flow456",
					},
				],
			});

			const result = transformEventToTrigger(event);

			expect(result.triggerTemplate).toBe("custom");
			expect(result.trigger).toEqual({
				type: "event",
				match: {
					"prefect.resource.id": "prefect.deployment.dep123",
				},
				match_related: {},
				after: [],
				expect: ["prefect.deployment.created"],
				for_each: [],
				posture: "Reactive",
				threshold: 1,
				within: 0,
			});
		});
	});

	describe("custom/unknown events", () => {
		it("creates basic custom trigger for unknown event types", () => {
			const event = createFakeEvent({
				event: "custom.my-app.user-action",
				resource: {
					"prefect.resource.id": "custom.resource.123",
				},
				related: [],
			});

			const result = transformEventToTrigger(event);

			expect(result.triggerTemplate).toBe("custom");
			expect(result.trigger).toEqual({
				type: "event",
				match: {
					"prefect.resource.id": "custom.resource.123",
				},
				match_related: {},
				after: [],
				expect: ["custom.my-app.user-action"],
				for_each: [],
				posture: "Reactive",
				threshold: 1,
				within: 0,
			});
		});

		it("creates basic custom trigger for events with related resources but no special handling", () => {
			const event = createFakeEvent({
				event: "my-service.order.completed",
				resource: {
					"prefect.resource.id": "my-service.order.order123",
				},
				related: [
					{
						"prefect.resource.role": "customer",
						"prefect.resource.id": "my-service.customer.cust456",
					},
				],
			});

			const result = transformEventToTrigger(event);

			// Custom events get empty match_related and for_each
			expect(result.trigger.match_related).toEqual({});
			expect(result.trigger.for_each).toEqual([]);
		});
	});

	describe("other prefect events", () => {
		it("creates basic custom trigger for task-run events", () => {
			const event = createFakeEvent({
				event: "prefect.task-run.Completed",
				resource: {
					"prefect.resource.id": "prefect.task-run.task123",
				},
				related: [],
			});

			const result = transformEventToTrigger(event);

			expect(result.triggerTemplate).toBe("custom");
			expect(result.trigger.match).toEqual({
				"prefect.resource.id": "prefect.task-run.task123",
			});
			expect(result.trigger.expect).toEqual(["prefect.task-run.Completed"]);
		});

		it("creates basic custom trigger for work-pool events", () => {
			const event = createFakeEvent({
				event: "prefect.work-pool.ready",
				resource: {
					"prefect.resource.id": "prefect.work-pool.pool123",
				},
				related: [],
			});

			const result = transformEventToTrigger(event);

			expect(result.triggerTemplate).toBe("custom");
			expect(result.trigger.expect).toEqual(["prefect.work-pool.ready"]);
		});
	});
});

describe("formatEventDate", () => {
	it("formats Date object to YYYY-MM-DD string", () => {
		const date = new Date("2024-01-15T10:30:00Z");
		expect(formatEventDate(date)).toBe("2024-01-15");
	});

	it("formats ISO string to YYYY-MM-DD string", () => {
		expect(formatEventDate("2024-01-15T10:30:00Z")).toBe("2024-01-15");
		expect(formatEventDate("2024-12-31T23:59:59.999Z")).toBe("2024-12-31");
	});

	it("handles dates at midnight", () => {
		const date = new Date("2024-06-01T00:00:00Z");
		expect(formatEventDate(date)).toBe("2024-06-01");
	});

	it("handles dates at end of day", () => {
		const date = new Date("2024-06-01T23:59:59.999Z");
		expect(formatEventDate(date)).toBe("2024-06-01");
	});
});
