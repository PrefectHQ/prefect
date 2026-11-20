import { describe, expect, it } from "vitest";
import { previewRRule } from "./rrule-schedule-preview";
import fixtures from "./rrule-schedule-preview.fixtures.json";

describe("RRule schedule preview", () => {
	it.each(fixtures)(
		"matches server get_dates for $name",
		({ timezone, start, rule, now, expected }) => {
			const result = previewRRule(
				`DTSTART;TZID=${timezone}:${start}\nRRULE:${rule}`,
				timezone,
				new Date(now),
			);
			expect(result.status).toBe("ready");
			if (result.status === "ready")
				expect(result.dates.map((date) => date.toISOString())).toEqual(
					expected,
				);
		},
	);
	it.each([
		["DAILY;INTERVAL=2", "2026-03-04T09:00:00.000Z"],
		["WEEKLY;INTERVAL=2;BYDAY=MO,WE", "2026-03-09T09:00:00.000Z"],
		["MONTHLY;BYMONTHDAY=31", "2026-03-31T09:00:00.000Z"],
		["MONTHLY;BYDAY=FR;BYSETPOS=-1", "2026-03-27T09:00:00.000Z"],
		["YEARLY;BYMONTH=2;BYMONTHDAY=29", "2028-02-29T09:00:00.000Z"],
	])("preserves interval phase and calendar filters for %s", (rule, first) => {
		const result = previewRRule(
			`DTSTART;TZID=UTC:20260101T090000\nRRULE:FREQ=${rule}`,
			"UTC",
			new Date("2026-03-02T10:00:00Z"),
		);
		expect(result.status).toBe("ready");
		if (result.status === "ready") {
			expect(result.dates).toHaveLength(5);
			expect(result.dates[0].toISOString()).toBe(first);
		}
	});
	it("includes an occurrence exactly at the query boundary", () => {
		const result = previewRRule(
			"DTSTART;TZID=UTC:20260301T090000\nRRULE:FREQ=DAILY",
			"UTC",
			new Date("2026-03-01T09:00:00Z"),
		);
		expect(result.status === "ready" && result.dates[0].toISOString()).toBe(
			"2026-03-01T09:00:00.000Z",
		);
	});
	it("returns an empty list for exhausted rules", () => {
		expect(
			previewRRule(
				"DTSTART;TZID=UTC:20260301T090000\nRRULE:FREQ=DAILY;UNTIL=20260302T235959Z",
				"UTC",
				new Date("2026-04-01Z"),
			),
		).toEqual({ status: "ready", dates: [] });
	});
	it("bounds impossible monthly patterns instead of hanging", () => {
		expect(
			previewRRule(
				"DTSTART;TZID=UTC:20260401T090000\nRRULE:FREQ=MONTHLY;INTERVAL=12;BYMONTHDAY=31",
				"UTC",
				new Date("2026-04-01Z"),
			),
		).toEqual({ status: "error" });
	});
	it("does not expand unsupported or invalid rules", () => {
		expect(previewRRule("nonsense", "UTC")).toEqual({ status: "unsupported" });
	});
});
