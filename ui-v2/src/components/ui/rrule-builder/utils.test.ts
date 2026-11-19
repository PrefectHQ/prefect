import { describe, expect, it } from "vitest";
import { parseRule, type RuleForm, serializeRule } from "./utils";

const examples: RuleForm[] = [
	{
		frequency: "DAILY",
		interval: 2,
		start: "2026-03-01",
		time: "09:30",
		weekdays: ["MO"],
		month: 3,
		day: 1,
		monthly: "day",
		position: 1,
		weekday: "MO",
		end: "never",
		until: "2026-12-31",
		count: 10,
	},
];
examples.push(
	{
		...examples[0],
		frequency: "WEEKLY",
		weekdays: ["MO", "WE"],
		end: "count",
		count: 8,
	},
	{ ...examples[0], frequency: "MONTHLY", day: 31 },
	{
		...examples[0],
		frequency: "MONTHLY",
		monthly: "weekday",
		position: 2,
		weekday: "TU",
	},
	{
		...examples[0],
		frequency: "MONTHLY",
		monthly: "weekday",
		position: -1,
		weekday: "FR",
		end: "until",
	},
	{ ...examples[0], frequency: "YEARLY", month: 2, day: 29 },
	{
		...examples[0],
		interval: 1,
		start: "2026-03-07",
		end: "until",
		until: "2026-03-10",
	},
);

describe("rrule-builder mapper", () => {
	it.each(examples)("round trips $frequency $monthly $end", (form) => {
		for (const timezone of ["UTC", "America/Chicago", "Asia/Kathmandu"]) {
			const rule = serializeRule(form, timezone);
			const parsed = parseRule(rule, timezone);
			expect(parsed.supported).toBe(true);
			if (parsed.supported)
				expect(serializeRule(parsed.value, timezone)).toBe(rule);
			expect(rule).toContain(
				`DTSTART;TZID=${timezone}:${form.start.replaceAll("-", "")}T093000`,
			);
		}
	});
	it("accepts ordinal BYDAY", () => {
		const parsed = parseRule(
			"DTSTART;TZID=UTC:20260301T093000\nRRULE:FREQ=MONTHLY;BYDAY=2TU",
		);
		expect(parsed.supported && parsed.value).toMatchObject({
			monthly: "weekday",
			position: 2,
			weekday: "TU",
		});
	});
	it.each([
		"FREQ=HOURLY",
		"FREQ=MINUTELY",
		"FREQ=SECONDLY",
		"FREQ=DAILY;BYWEEKNO=2",
		"FREQ=DAILY;BYYEARDAY=10",
		"FREQ=DAILY;BYHOUR=9,10",
		"FREQ=DAILY;BYMINUTE=0,30",
		"FREQ=DAILY;BYSECOND=1",
		"FREQ=DAILY;BYMONTH=2",
		"FREQ=DAILY;BYDAY=MO",
		"FREQ=WEEKLY;BYDAY=2TU",
		"FREQ=MONTHLY;BYMONTHDAY=1,2",
		"FREQ=MONTHLY;BYMONTHDAY=-1",
		"FREQ=MONTHLY;BYDAY=MO,TU;BYSETPOS=1",
		"FREQ=MONTHLY;BYDAY=MO;BYSETPOS=-2",
		"FREQ=YEARLY;BYMONTH=1,2",
		"FREQ=YEARLY;BYDAY=MO",
		"FREQ=DAILY;COUNT=2;UNTIL=20261231T235959Z",
		"FREQ=DAILY;WKST=SU",
		"FREQ=DAILY;INTERVAL=0",
		"FREQ=DAILY;COUNT=0",
		"FREQ=DAILY;UNTIL=20261231T120000Z",
		"FREQ=DAILY;BYEASTER=1",
		"FREQ=DAILY;FREQ=WEEKLY",
	])("rejects unrepresentable rule %s", (rule) => {
		expect(
			parseRule(`DTSTART;TZID=UTC:20260301T093000\nRRULE:${rule}`).supported,
		).toBe(false);
	});
	it.each([
		"EXDATE:20260302T093000Z",
		"RDATE:20260302T093000Z",
		"EXRULE:FREQ=DAILY",
		"RRULE:FREQ=WEEKLY",
	])("rejects extra line %s", (line) => {
		expect(parseRule(`${serializeRule(examples[0])}\n${line}`).supported).toBe(
			false,
		);
	});
	it.each([
		"",
		"nonsense",
		"RRULE:FREQ=DAILY",
		"DTSTART;TZID=UTC:20260230T093000\nRRULE:FREQ=DAILY",
	])("rejects invalid or missing start %s", (rule) => {
		expect(parseRule(rule).supported).toBe(false);
	});
	it("does not reinterpret another timezone", () => {
		expect(
			parseRule(serializeRule(examples[0], "America/Chicago"), "UTC").supported,
		).toBe(false);
	});
	it("does not assign a timezone to a floating DTSTART", () => {
		expect(
			parseRule("DTSTART:20260301T093000\nRRULE:FREQ=DAILY", "America/Chicago")
				.supported,
		).toBe(false);
	});
	it("rejects dates outside the server's year range", () => {
		expect(() =>
			serializeRule({ ...examples[0], start: "0000-01-01" }),
		).toThrow();
	});
	it("rejects invalid form values", () => {
		expect(() => serializeRule({ ...examples[0], interval: 0 })).toThrow();
		expect(() =>
			serializeRule({ ...examples[0], frequency: "WEEKLY", weekdays: [] }),
		).toThrow();
	});
});
