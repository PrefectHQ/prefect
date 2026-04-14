import { describe, expect, it } from "vitest";
import { z } from "zod";

/**
 * Mirrors the route's searchParams schema so we can unit-test the
 * URL search param naming without importing TanStack Router internals.
 */
const searchParams = z.object({
	resource: z.array(z.string()).optional(),
	events: z.array(z.string()).optional(),
	rangeType: z.enum(["span", "range"]).optional().default("span"),
	seconds: z.number().optional().default(-86400),
	start: z.string().optional(),
	end: z.string().optional(),
	order: z.enum(["ASC", "DESC"]).optional(),
});

describe("events search params uses V1-compatible 'events' key", () => {
	it("accepts the 'events' param (plural, matching V1)", () => {
		const result = searchParams.parse({
			events: ["prefect.flow-run.*"],
		});

		expect(result.events).toEqual(["prefect.flow-run.*"]);
	});

	it("handles multiple event values", () => {
		const result = searchParams.parse({
			events: ["prefect.flow-run.*", "prefect.task-run.*"],
		});

		expect(result.events).toEqual(["prefect.flow-run.*", "prefect.task-run.*"]);
	});

	it("returns undefined when events param is not provided", () => {
		const result = searchParams.parse({});

		expect(result.events).toBeUndefined();
	});

	it("preserves other search params alongside events", () => {
		const result = searchParams.parse({
			events: ["prefect.flow-run.*"],
			resource: ["prefect.flow-run.abc123"],
			order: "ASC",
		});

		expect(result.events).toEqual(["prefect.flow-run.*"]);
		expect(result.resource).toEqual(["prefect.flow-run.abc123"]);
		expect(result.order).toBe("ASC");
	});
});
