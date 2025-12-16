import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
	buildEventsCountFilterFromSearch,
	buildEventsFilterFromSearch,
	calculateTimeUnit,
	DEFAULT_EXCLUDE_EVENTS,
	type EventsSearchParams,
	getDateRangeFromSearch,
} from "./filters";

describe("events filter utilities", () => {
	describe("DEFAULT_EXCLUDE_EVENTS", () => {
		it("contains prefect.log.write", () => {
			expect(DEFAULT_EXCLUDE_EVENTS).toContain("prefect.log.write");
		});

		it("is an array with expected default exclusions", () => {
			expect(DEFAULT_EXCLUDE_EVENTS).toEqual(["prefect.log.write"]);
		});
	});

	describe("getDateRangeFromSearch", () => {
		beforeEach(() => {
			vi.useFakeTimers();
			vi.setSystemTime(new Date("2024-01-15T12:30:45.123Z"));
		});

		afterEach(() => {
			vi.useRealTimers();
		});

		describe("span mode", () => {
			it("calculates date range for negative seconds (past)", () => {
				const result = getDateRangeFromSearch({
					rangeType: "span",
					seconds: -86400, // 24 hours ago
				});

				// Rounded to minute: 2024-01-15T12:30:00.000Z
				// 24 hours ago: 2024-01-14T12:30:00.000Z
				expect(result.from).toBe("2024-01-14T12:30:00.000Z");
				expect(result.to).toBe("2024-01-15T12:30:00.000Z");
			});

			it("calculates date range for positive seconds (future)", () => {
				const result = getDateRangeFromSearch({
					rangeType: "span",
					seconds: 3600, // 1 hour in future
				});

				// Should sort dates so from < to
				expect(result.from).toBe("2024-01-15T12:30:00.000Z");
				expect(result.to).toBe("2024-01-15T13:30:00.000Z");
			});

			it("uses default of -86400 seconds when seconds not provided", () => {
				const result = getDateRangeFromSearch({
					rangeType: "span",
				});

				expect(result.from).toBe("2024-01-14T12:30:00.000Z");
				expect(result.to).toBe("2024-01-15T12:30:00.000Z");
			});

			it("uses span mode as default when rangeType not specified", () => {
				const result = getDateRangeFromSearch({});

				expect(result.from).toBe("2024-01-14T12:30:00.000Z");
				expect(result.to).toBe("2024-01-15T12:30:00.000Z");
			});

			it("handles short time spans", () => {
				const result = getDateRangeFromSearch({
					rangeType: "span",
					seconds: -3600, // 1 hour ago
				});

				expect(result.from).toBe("2024-01-15T11:30:00.000Z");
				expect(result.to).toBe("2024-01-15T12:30:00.000Z");
			});

			it("handles week-long time spans", () => {
				const result = getDateRangeFromSearch({
					rangeType: "span",
					seconds: -604800, // 7 days ago
				});

				expect(result.from).toBe("2024-01-08T12:30:00.000Z");
				expect(result.to).toBe("2024-01-15T12:30:00.000Z");
			});
		});

		describe("range mode", () => {
			it("uses explicit start and end dates", () => {
				const result = getDateRangeFromSearch({
					rangeType: "range",
					start: "2024-01-01T00:00:00.000Z",
					end: "2024-01-31T23:59:59.999Z",
				});

				expect(result.from).toBe("2024-01-01T00:00:00.000Z");
				expect(result.to).toBe("2024-01-31T23:59:59.999Z");
			});

			it("falls back to default when start is missing", () => {
				const result = getDateRangeFromSearch({
					rangeType: "range",
					end: "2024-01-31T23:59:59.999Z",
				});

				// Should fall back to last 24 hours
				expect(result.from).toBe("2024-01-14T12:30:00.000Z");
				expect(result.to).toBe("2024-01-15T12:30:00.000Z");
			});

			it("falls back to default when end is missing", () => {
				const result = getDateRangeFromSearch({
					rangeType: "range",
					start: "2024-01-01T00:00:00.000Z",
				});

				// Should fall back to last 24 hours
				expect(result.from).toBe("2024-01-14T12:30:00.000Z");
				expect(result.to).toBe("2024-01-15T12:30:00.000Z");
			});
		});
	});

	describe("calculateTimeUnit", () => {
		it("returns 'minute' for ranges under 1000 minutes", () => {
			// 1 hour = 60 minutes
			const result = calculateTimeUnit(
				"2024-01-15T10:00:00.000Z",
				"2024-01-15T11:00:00.000Z",
			);
			expect(result).toBe("minute");
		});

		it("returns 'minute' for ranges exactly at 1000 minutes", () => {
			// 1000 minutes = 16.67 hours
			const start = new Date("2024-01-15T00:00:00.000Z");
			const end = new Date(start.getTime() + 1000 * 60 * 1000);

			const result = calculateTimeUnit(start.toISOString(), end.toISOString());
			expect(result).toBe("minute");
		});

		it("returns 'hour' for ranges over 1000 minutes but under 1000 hours", () => {
			// 24 hours = 1440 minutes > 1000
			const result = calculateTimeUnit(
				"2024-01-15T00:00:00.000Z",
				"2024-01-16T00:00:00.000Z",
			);
			expect(result).toBe("hour");
		});

		it("returns 'hour' for ranges exactly at 1000 hours", () => {
			// 1000 hours = ~41.67 days
			const start = new Date("2024-01-01T00:00:00.000Z");
			const end = new Date(start.getTime() + 1000 * 60 * 60 * 1000);

			const result = calculateTimeUnit(start.toISOString(), end.toISOString());
			expect(result).toBe("hour");
		});

		it("returns 'day' for ranges over 1000 hours", () => {
			// 60 days = 1440 hours > 1000
			const result = calculateTimeUnit(
				"2024-01-01T00:00:00.000Z",
				"2024-03-01T00:00:00.000Z",
			);
			expect(result).toBe("day");
		});

		it("accepts Date objects as input", () => {
			const start = new Date("2024-01-15T10:00:00.000Z");
			const end = new Date("2024-01-15T11:00:00.000Z");

			const result = calculateTimeUnit(start, end);
			expect(result).toBe("minute");
		});

		it("handles dates in reverse order", () => {
			// Uses Math.abs so order doesn't matter
			const result = calculateTimeUnit(
				"2024-01-16T00:00:00.000Z",
				"2024-01-15T00:00:00.000Z",
			);
			expect(result).toBe("hour");
		});

		describe("boundary conditions for bucket validation", () => {
			it("returns 'minute' for 16 hour range (960 minutes)", () => {
				const result = calculateTimeUnit(
					"2024-01-15T00:00:00.000Z",
					"2024-01-15T16:00:00.000Z",
				);
				expect(result).toBe("minute");
			});

			it("returns 'hour' for 17 hour range (1020 minutes)", () => {
				const result = calculateTimeUnit(
					"2024-01-15T00:00:00.000Z",
					"2024-01-15T17:00:00.000Z",
				);
				expect(result).toBe("hour");
			});

			it("returns 'hour' for 41 day range (984 hours)", () => {
				const result = calculateTimeUnit(
					"2024-01-01T00:00:00.000Z",
					"2024-02-11T00:00:00.000Z",
				);
				expect(result).toBe("hour");
			});

			it("returns 'day' for 42 day range (1008 hours)", () => {
				const result = calculateTimeUnit(
					"2024-01-01T00:00:00.000Z",
					"2024-02-12T00:00:00.000Z",
				);
				expect(result).toBe("day");
			});
		});
	});

	describe("buildEventsFilterFromSearch", () => {
		beforeEach(() => {
			vi.useFakeTimers();
			vi.setSystemTime(new Date("2024-01-15T12:30:45.123Z"));
		});

		afterEach(() => {
			vi.useRealTimers();
		});

		it("builds filter with default values", () => {
			const result = buildEventsFilterFromSearch({});

			expect(result).toEqual({
				filter: {
					occurred: {
						since: "2024-01-14T12:30:00.000Z",
						until: "2024-01-15T12:30:00.000Z",
					},
					order: "DESC",
					event: {
						exclude_prefix: ["prefect.log.write"],
					},
				},
				limit: 50,
			});
		});

		it("includes resource filter when resource IDs provided", () => {
			const result = buildEventsFilterFromSearch({
				resource: ["prefect.flow-run.abc123", "prefect.task-run.def456"],
			});

			expect(result.filter?.any_resource).toEqual({
				id_prefix: ["prefect.flow-run.abc123", "prefect.task-run.def456"],
			});
		});

		it("includes event prefix filter when event names provided", () => {
			const result = buildEventsFilterFromSearch({
				event: ["prefect.flow-run.", "prefect.deployment."],
			});

			expect(result.filter?.event).toEqual({
				prefix: ["prefect.flow-run.", "prefect.deployment."],
				exclude_prefix: ["prefect.log.write"],
			});
		});

		it("respects custom order", () => {
			const result = buildEventsFilterFromSearch({
				order: "ASC",
			});

			expect(result.filter?.order).toBe("ASC");
		});

		it("uses range mode when specified", () => {
			const result = buildEventsFilterFromSearch({
				rangeType: "range",
				start: "2024-01-01T00:00:00.000Z",
				end: "2024-01-31T23:59:59.999Z",
			});

			expect(result.filter?.occurred).toEqual({
				since: "2024-01-01T00:00:00.000Z",
				until: "2024-01-31T23:59:59.999Z",
			});
		});

		it("uses span mode with custom seconds", () => {
			const result = buildEventsFilterFromSearch({
				rangeType: "span",
				seconds: -3600, // 1 hour
			});

			expect(result.filter?.occurred).toEqual({
				since: "2024-01-15T11:30:00.000Z",
				until: "2024-01-15T12:30:00.000Z",
			});
		});

		it("always includes default event exclusions", () => {
			const result = buildEventsFilterFromSearch({
				event: ["prefect.flow-run."],
			});

			expect(result.filter?.event?.exclude_prefix).toEqual([
				"prefect.log.write",
			]);
		});

		it("combines all filter options", () => {
			const search: EventsSearchParams = {
				rangeType: "range",
				start: "2024-01-01T00:00:00.000Z",
				end: "2024-01-31T23:59:59.999Z",
				resource: ["prefect.flow-run.abc123"],
				event: ["prefect.flow-run.completed"],
				order: "ASC",
			};

			const result = buildEventsFilterFromSearch(search);

			expect(result).toEqual({
				filter: {
					occurred: {
						since: "2024-01-01T00:00:00.000Z",
						until: "2024-01-31T23:59:59.999Z",
					},
					order: "ASC",
					any_resource: {
						id_prefix: ["prefect.flow-run.abc123"],
					},
					event: {
						prefix: ["prefect.flow-run.completed"],
						exclude_prefix: ["prefect.log.write"],
					},
				},
				limit: 50,
			});
		});

		it("does not include resource filter when empty array provided", () => {
			const result = buildEventsFilterFromSearch({
				resource: [],
			});

			expect(result.filter?.any_resource).toBeUndefined();
		});

		it("does not include event prefix when empty array provided", () => {
			const result = buildEventsFilterFromSearch({
				event: [],
			});

			expect(result.filter?.event?.prefix).toBeUndefined();
			expect(result.filter?.event?.exclude_prefix).toEqual([
				"prefect.log.write",
			]);
		});
	});

	describe("buildEventsCountFilterFromSearch", () => {
		beforeEach(() => {
			vi.useFakeTimers();
			vi.setSystemTime(new Date("2024-01-15T12:30:45.123Z"));
		});

		afterEach(() => {
			vi.useRealTimers();
		});

		it("builds count filter with default values", () => {
			const result = buildEventsCountFilterFromSearch({});

			expect(result).toEqual({
				filter: {
					occurred: {
						since: "2024-01-14T12:30:00.000Z",
						until: "2024-01-15T12:30:00.000Z",
					},
					order: "DESC",
					event: {
						exclude_prefix: ["prefect.log.write"],
					},
				},
				time_unit: "hour", // 24 hours = 1440 minutes > 1000, so hour
				time_interval: 1,
			});
		});

		it("calculates appropriate time_unit for short ranges", () => {
			const result = buildEventsCountFilterFromSearch({
				rangeType: "span",
				seconds: -3600, // 1 hour = 60 minutes
			});

			expect(result.time_unit).toBe("minute");
		});

		it("calculates appropriate time_unit for medium ranges", () => {
			const result = buildEventsCountFilterFromSearch({
				rangeType: "span",
				seconds: -86400, // 24 hours = 1440 minutes
			});

			expect(result.time_unit).toBe("hour");
		});

		it("calculates appropriate time_unit for large ranges", () => {
			const result = buildEventsCountFilterFromSearch({
				rangeType: "range",
				start: "2024-01-01T00:00:00.000Z",
				end: "2024-03-01T00:00:00.000Z", // 60 days
			});

			expect(result.time_unit).toBe("day");
		});

		it("includes resource filter when resource IDs provided", () => {
			const result = buildEventsCountFilterFromSearch({
				resource: ["prefect.flow-run.abc123"],
			});

			expect(result.filter?.any_resource).toEqual({
				id_prefix: ["prefect.flow-run.abc123"],
			});
		});

		it("includes event prefix filter when event names provided", () => {
			const result = buildEventsCountFilterFromSearch({
				event: ["prefect.flow-run."],
			});

			expect(result.filter?.event).toEqual({
				prefix: ["prefect.flow-run."],
				exclude_prefix: ["prefect.log.write"],
			});
		});

		it("always sets time_interval to 1", () => {
			const result = buildEventsCountFilterFromSearch({});
			expect(result.time_interval).toBe(1);
		});

		it("combines all filter options", () => {
			const search: EventsSearchParams = {
				rangeType: "span",
				seconds: -3600, // 1 hour
				resource: ["prefect.flow-run.abc123"],
				event: ["prefect.flow-run.completed"],
				order: "ASC",
			};

			const result = buildEventsCountFilterFromSearch(search);

			expect(result).toEqual({
				filter: {
					occurred: {
						since: "2024-01-15T11:30:00.000Z",
						until: "2024-01-15T12:30:00.000Z",
					},
					order: "ASC",
					any_resource: {
						id_prefix: ["prefect.flow-run.abc123"],
					},
					event: {
						prefix: ["prefect.flow-run.completed"],
						exclude_prefix: ["prefect.log.write"],
					},
				},
				time_unit: "minute",
				time_interval: 1,
			});
		});

		it("respects custom order", () => {
			const result = buildEventsCountFilterFromSearch({
				order: "ASC",
			});

			expect(result.filter?.order).toBe("ASC");
		});
	});

	describe("type compatibility", () => {
		it("buildEventsFilterFromSearch returns EventsFilter type", () => {
			const result = buildEventsFilterFromSearch({});

			// Type check: should have filter and limit properties
			expect(result).toHaveProperty("filter");
			expect(result).toHaveProperty("limit");
			expect(typeof result.limit).toBe("number");
		});

		it("buildEventsCountFilterFromSearch returns EventsCountFilter type", () => {
			const result = buildEventsCountFilterFromSearch({});

			// Type check: should have filter, time_unit, and time_interval properties
			expect(result).toHaveProperty("filter");
			expect(result).toHaveProperty("time_unit");
			expect(result).toHaveProperty("time_interval");
			expect(["minute", "hour", "day", "week", "second"]).toContain(
				result.time_unit,
			);
			expect(typeof result.time_interval).toBe("number");
		});
	});
});
