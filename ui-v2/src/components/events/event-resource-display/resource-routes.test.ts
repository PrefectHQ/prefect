import { describe, expect, it } from "vitest";
import { getResourceRoute } from "./resource-routes";

describe("getResourceRoute", () => {
	it("returns correct route for flow-run resources", () => {
		const resource = {
			"prefect.resource.id": "prefect.flow-run.abc-123",
			"prefect.resource.role": "flow-run",
		};
		const route = getResourceRoute(resource);
		expect(route).toEqual({
			to: "/runs/flow-run/$id",
			params: { id: "abc-123" },
		});
	});

	it("returns correct route for task-run resources", () => {
		const resource = {
			"prefect.resource.id": "prefect.task-run.def-456",
			"prefect.resource.role": "task-run",
		};
		const route = getResourceRoute(resource);
		expect(route).toEqual({
			to: "/runs/task-run/$id",
			params: { id: "def-456" },
		});
	});

	it("returns correct route for deployment resources", () => {
		const resource = {
			"prefect.resource.id": "prefect.deployment.ghi-789",
			"prefect.resource.role": "deployment",
		};
		const route = getResourceRoute(resource);
		expect(route).toEqual({
			to: "/deployments/deployment/$id",
			params: { id: "ghi-789" },
		});
	});

	it("returns correct route for flow resources", () => {
		const resource = {
			"prefect.resource.id": "prefect.flow.jkl-012",
			"prefect.resource.role": "flow",
		};
		const route = getResourceRoute(resource);
		expect(route).toEqual({
			to: "/flows/flow/$id",
			params: { id: "jkl-012" },
		});
	});

	it("returns correct route for work-pool resources using name", () => {
		const resource = {
			"prefect.resource.id": "prefect.work-pool.pool-id-123",
			"prefect.resource.role": "work-pool",
			"prefect.resource.name": "my-work-pool",
		};
		const route = getResourceRoute(resource);
		expect(route).toEqual({
			to: "/work-pools/work-pool/$workPoolName",
			params: { workPoolName: "my-work-pool" },
		});
	});

	it("returns correct route for work-pool resources using id when name is not available", () => {
		const resource = {
			"prefect.resource.id": "prefect.work-pool.pool-id-123",
			"prefect.resource.role": "work-pool",
		};
		const route = getResourceRoute(resource);
		expect(route).toEqual({
			to: "/work-pools/work-pool/$workPoolName",
			params: { workPoolName: "pool-id-123" },
		});
	});

	it("returns correct route for automation resources", () => {
		const resource = {
			"prefect.resource.id": "prefect.automation.auto-123",
			"prefect.resource.role": "automation",
		};
		const route = getResourceRoute(resource);
		expect(route).toEqual({
			to: "/automations/automation/$id",
			params: { id: "auto-123" },
		});
	});

	it("returns correct route for block-document resources", () => {
		const resource = {
			"prefect.resource.id": "prefect.block-document.block-123",
			"prefect.resource.role": "block-document",
		};
		const route = getResourceRoute(resource);
		expect(route).toEqual({
			to: "/blocks/block/$id",
			params: { id: "block-123" },
		});
	});

	it("returns correct route for concurrency-limit resources", () => {
		const resource = {
			"prefect.resource.id": "prefect.concurrency-limit.limit-123",
			"prefect.resource.role": "concurrency-limit",
		};
		const route = getResourceRoute(resource);
		expect(route).toEqual({
			to: "/concurrency-limits/concurrency-limit/$id",
			params: { id: "limit-123" },
		});
	});

	it("returns null for work-queue resources without related work pool", () => {
		const resource = {
			"prefect.resource.id": "prefect.work-queue.queue-123",
			"prefect.resource.role": "work-queue",
			"prefect.resource.name": "default",
		};
		const route = getResourceRoute(resource);
		expect(route).toBeNull();
	});

	it("returns null for work-queue resources without queue name", () => {
		const resource = {
			"prefect.resource.id": "prefect.work-queue.queue-123",
			"prefect.resource.role": "work-queue",
		};
		const relatedResources = [
			{
				"prefect.resource.id": "prefect.work-pool.pool-456",
				"prefect.resource.role": "work-pool",
				"prefect.resource.name": "my-pool",
			},
		];
		const route = getResourceRoute(resource, relatedResources);
		expect(route).toBeNull();
	});

	it("returns correct route for work-queue resources with related work pool", () => {
		const resource = {
			"prefect.resource.id": "prefect.work-queue.queue-123",
			"prefect.resource.role": "work-queue",
			"prefect.resource.name": "default",
		};
		const relatedResources = [
			{
				"prefect.resource.id": "prefect.work-pool.pool-456",
				"prefect.resource.role": "work-pool",
				"prefect.resource.name": "my-pool",
			},
		];
		const route = getResourceRoute(resource, relatedResources);
		expect(route).toEqual({
			to: "/work-pools/work-pool/$workPoolName/queue/$workQueueName",
			params: { workPoolName: "my-pool", workQueueName: "default" },
		});
	});

	it("returns correct route for work-queue with work pool using extracted id when name is not available", () => {
		const resource = {
			"prefect.resource.id": "prefect.work-queue.queue-123",
			"prefect.resource.role": "work-queue",
			"prefect.resource.name": "my-queue",
		};
		const relatedResources = [
			{
				"prefect.resource.id": "prefect.work-pool.pool-456",
				"prefect.resource.role": "work-pool",
			},
		];
		const route = getResourceRoute(resource, relatedResources);
		expect(route).toEqual({
			to: "/work-pools/work-pool/$workPoolName/queue/$workQueueName",
			params: { workPoolName: "pool-456", workQueueName: "my-queue" },
		});
	});

	it("returns null for unknown resource types", () => {
		const resource = {
			"prefect.resource.id": "prefect.unknown.xyz-123",
			"prefect.resource.role": "unknown",
		};
		const route = getResourceRoute(resource);
		expect(route).toBeNull();
	});

	it("returns null when resource id is missing", () => {
		const resource = {
			"prefect.resource.role": "flow-run",
		};
		const route = getResourceRoute(resource);
		expect(route).toBeNull();
	});

	it("returns null when resource id cannot be extracted", () => {
		const resource = {
			"prefect.resource.id": "prefect.flow-run",
			"prefect.resource.role": "flow-run",
		};
		const route = getResourceRoute(resource);
		expect(route).toBeNull();
	});

	it("handles resource ids with multiple dots", () => {
		const resource = {
			"prefect.resource.id": "prefect.flow-run.abc.def.ghi",
			"prefect.resource.role": "flow-run",
		};
		const route = getResourceRoute(resource);
		expect(route).toEqual({
			to: "/runs/flow-run/$id",
			params: { id: "abc.def.ghi" },
		});
	});
});
