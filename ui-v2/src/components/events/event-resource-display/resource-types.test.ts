import { describe, expect, it } from "vitest";
import {
	extractResourceId,
	parseResourceType,
	RESOURCE_ICONS,
	type ResourceType,
} from "./resource-types";

describe("parseResourceType", () => {
	it("parses flow-run resource type", () => {
		expect(parseResourceType("prefect.flow-run.abc-123")).toBe("flow-run");
		expect(parseResourceType("prefect.flow-run.")).toBe("flow-run");
		expect(
			parseResourceType(
				"prefect.flow-run.12345678-1234-1234-1234-123456789012",
			),
		).toBe("flow-run");
	});

	it("parses task-run resource type", () => {
		expect(parseResourceType("prefect.task-run.abc-123")).toBe("task-run");
		expect(parseResourceType("prefect.task-run.")).toBe("task-run");
		expect(
			parseResourceType(
				"prefect.task-run.12345678-1234-1234-1234-123456789012",
			),
		).toBe("task-run");
	});

	it("parses deployment resource type", () => {
		expect(parseResourceType("prefect.deployment.abc-123")).toBe("deployment");
		expect(parseResourceType("prefect.deployment.")).toBe("deployment");
	});

	it("parses flow resource type", () => {
		expect(parseResourceType("prefect.flow.abc-123")).toBe("flow");
		expect(parseResourceType("prefect.flow.")).toBe("flow");
	});

	it("parses work-pool resource type", () => {
		expect(parseResourceType("prefect.work-pool.abc-123")).toBe("work-pool");
		expect(parseResourceType("prefect.work-pool.")).toBe("work-pool");
	});

	it("parses work-queue resource type", () => {
		expect(parseResourceType("prefect.work-queue.abc-123")).toBe("work-queue");
		expect(parseResourceType("prefect.work-queue.")).toBe("work-queue");
	});

	it("parses automation resource type", () => {
		expect(parseResourceType("prefect.automation.abc-123")).toBe("automation");
		expect(parseResourceType("prefect.automation.")).toBe("automation");
	});

	it("parses block-document resource type", () => {
		expect(parseResourceType("prefect.block-document.abc-123")).toBe(
			"block-document",
		);
		expect(parseResourceType("prefect.block-document.")).toBe("block-document");
	});

	it("parses concurrency-limit resource type", () => {
		expect(parseResourceType("prefect.concurrency-limit.abc-123")).toBe(
			"concurrency-limit",
		);
		expect(parseResourceType("prefect.concurrency-limit.")).toBe(
			"concurrency-limit",
		);
	});

	it("returns unknown for unrecognized prefixes", () => {
		expect(parseResourceType("prefect.unknown-type.abc-123")).toBe("unknown");
		expect(parseResourceType("other.flow-run.abc-123")).toBe("unknown");
		expect(parseResourceType("random-string")).toBe("unknown");
	});

	it("returns unknown for empty or invalid input", () => {
		expect(parseResourceType("")).toBe("unknown");
		expect(parseResourceType(null as unknown as string)).toBe("unknown");
		expect(parseResourceType(undefined as unknown as string)).toBe("unknown");
		expect(parseResourceType(123 as unknown as string)).toBe("unknown");
	});
});

describe("extractResourceId", () => {
	it("extracts ID from valid resource IDs", () => {
		expect(extractResourceId("prefect.flow-run.abc-123")).toBe("abc-123");
		expect(extractResourceId("prefect.deployment.my-deployment")).toBe(
			"my-deployment",
		);
		expect(
			extractResourceId("prefect.flow.12345678-1234-1234-1234-123456789012"),
		).toBe("12345678-1234-1234-1234-123456789012");
	});

	it("handles IDs with multiple dots", () => {
		expect(extractResourceId("prefect.flow-run.abc.def.ghi")).toBe(
			"abc.def.ghi",
		);
		expect(extractResourceId("prefect.block-document.my.block.name")).toBe(
			"my.block.name",
		);
	});

	it("returns null for invalid formats", () => {
		expect(extractResourceId("prefect.flow-run")).toBe(null);
		expect(extractResourceId("prefect")).toBe(null);
		expect(extractResourceId("single")).toBe(null);
	});

	it("returns null for empty or invalid input", () => {
		expect(extractResourceId("")).toBe(null);
		expect(extractResourceId(null as unknown as string)).toBe(null);
		expect(extractResourceId(undefined as unknown as string)).toBe(null);
		expect(extractResourceId(123 as unknown as string)).toBe(null);
	});

	it("handles edge cases with empty parts", () => {
		expect(extractResourceId("prefect.flow-run.")).toBe("");
		expect(extractResourceId("prefect..abc")).toBe("abc");
	});
});

describe("RESOURCE_ICONS", () => {
	it("has an icon mapping for each resource type", () => {
		const resourceTypes: ResourceType[] = [
			"flow-run",
			"task-run",
			"deployment",
			"flow",
			"work-pool",
			"work-queue",
			"automation",
			"block-document",
			"concurrency-limit",
			"unknown",
		];

		for (const type of resourceTypes) {
			expect(RESOURCE_ICONS[type]).toBeDefined();
			expect(typeof RESOURCE_ICONS[type]).toBe("string");
		}
	});

	it("maps to expected icon names", () => {
		expect(RESOURCE_ICONS["flow-run"]).toBe("Play");
		expect(RESOURCE_ICONS["task-run"]).toBe("Cog");
		expect(RESOURCE_ICONS.deployment).toBe("Rocket");
		expect(RESOURCE_ICONS.flow).toBe("Workflow");
		expect(RESOURCE_ICONS["work-pool"]).toBe("Server");
		expect(RESOURCE_ICONS["work-queue"]).toBe("ListOrdered");
		expect(RESOURCE_ICONS.automation).toBe("Zap");
		expect(RESOURCE_ICONS["block-document"]).toBe("Box");
		expect(RESOURCE_ICONS["concurrency-limit"]).toBe("Gauge");
		expect(RESOURCE_ICONS.unknown).toBe("Circle");
	});
});
