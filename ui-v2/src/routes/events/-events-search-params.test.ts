import { describe, expect, it } from "vitest";
import { z } from "zod";

/**
 * Duplicates the route's searchParams schema so we can unit-test the
 * V1 → V2 backward-compatibility transform without importing the route
 * (which pulls in TanStack Router internals).
 */
const searchParams = z
	.object({
		resource: z.array(z.string()).optional(),
		event: z.array(z.string()).optional(),
		events: z.array(z.string()).optional(),
		rangeType: z.enum(["span", "range"]).optional().default("span"),
		seconds: z.number().optional().default(-86400),
		start: z.string().optional(),
		end: z.string().optional(),
		order: z.enum(["ASC", "DESC"]).optional(),
	})
	.transform(({ events, ...rest }) => ({
		...rest,
		event: rest.event ?? events,
	}));

describe("events search params V1 backward compatibility", () => {
	it("maps V1 'events' param to 'event'", () => {
		const result = searchParams.parse({
			events: ["prefect.flow-run.*"],
		});

		expect(result.event).toEqual(["prefect.flow-run.*"]);
		expect(result).not.toHaveProperty("events");
	});

	it("preserves V2 'event' param as-is", () => {
		const result = searchParams.parse({
			event: ["prefect.flow-run.Completed"],
		});

		expect(result.event).toEqual(["prefect.flow-run.Completed"]);
	});

	it("prefers V2 'event' over V1 'events' when both are present", () => {
		const result = searchParams.parse({
			event: ["prefect.flow-run.Completed"],
			events: ["prefect.task-run.*"],
		});

		expect(result.event).toEqual(["prefect.flow-run.Completed"]);
	});

	it("returns undefined event when neither param is provided", () => {
		const result = searchParams.parse({});

		expect(result.event).toBeUndefined();
	});

	it("handles multiple V1 event values", () => {
		const result = searchParams.parse({
			events: ["prefect.flow-run.*", "prefect.task-run.*"],
		});

		expect(result.event).toEqual(["prefect.flow-run.*", "prefect.task-run.*"]);
	});

	it("preserves other search params alongside V1 events", () => {
		const result = searchParams.parse({
			events: ["prefect.flow-run.*"],
			resource: ["prefect.flow-run.abc123"],
			order: "ASC",
		});

		expect(result.event).toEqual(["prefect.flow-run.*"]);
		expect(result.resource).toEqual(["prefect.flow-run.abc123"]);
		expect(result.order).toBe("ASC");
	});
});
