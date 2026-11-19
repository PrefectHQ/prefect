import { describe, expect, it } from "vitest";
import {
	getAnnualLabel,
	getMonthlyOptions,
	parseRule,
	type RuleForm,
	ruleFormSchema,
	serializeRule,
} from "./utils";

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
	it("derives monthly options from the start date and only offers last in the final week", () => {
		const value = { ...examples[0], start: "2026-11-19", day: 19 };
		expect(
			getMonthlyOptions(value).options.map((option) => option.label),
		).toEqual(["Monthly on day 19", "Monthly on the third Thursday"]);
		expect(
			getMonthlyOptions({ ...value, start: "2026-11-26", day: 26 }).options.map(
				(option) => option.label,
			),
		).toEqual([
			"Monthly on day 26",
			"Monthly on the fourth Thursday",
			"Monthly on the last Thursday",
		]);
	});
	it("preserves a nonmatching monthly day and handles temporarily invalid starts", () => {
		const value = { ...examples[0], start: "2026-11-19", day: 31 };
		expect(getMonthlyOptions(value).selected).toBe("day:31");
		expect(getMonthlyOptions(value).options.at(-1)?.label).toBe(
			"Monthly on day 31",
		);
		expect(
			getMonthlyOptions({ ...value, start: "" }).options.map(
				(option) => option.label,
			),
		).toEqual(["Monthly on day 31"]);
		expect(getAnnualLabel({ ...value, start: "invalid" })).toBeNull();
		expect(getAnnualLabel({ ...value, month: 11, day: 19 })).toBe(
			"Annually on November 19",
		);
	});
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
	it("rejects yearly month-day expansion without narrowing it to the start month", () => {
		expect(
			parseRule(
				"DTSTART;TZID=UTC:20260301T093000\nRRULE:FREQ=YEARLY;BYMONTHDAY=15",
			),
		).toEqual({
			supported: false,
			reason: "Yearly day-of-month filters require an explicit month.",
		});
	});
	it.each([
		["Asia/Kathmandu", "21:00"],
		["America/Chicago", "00:15"],
		["America/Chicago", "23:45"],
	])(
		"uses server-local end-of-day clock fields for %s at %s",
		(timezone, time) => {
			const rule = serializeRule(
				{ ...examples[0], time, end: "until", until: "2026-03-10" },
				timezone,
			);
			expect(rule).toContain("UNTIL=20260310T235959Z");
			const parsed = parseRule(rule, timezone);
			expect(parsed.supported && parsed.value.until).toBe("2026-03-10");
			if (parsed.supported)
				expect(serializeRule(parsed.value, timezone)).toBe(rule);
		},
	);
	it.each(["never", "until"] as const)(
		"ignores and normalizes a cleared count when ending with %s",
		(end) => {
			const form = { ...examples[0], end, count: Number.NaN };
			expect(serializeRule(form)).not.toContain("COUNT=");
			expect(ruleFormSchema.parse(form).count).toBe(10);
			expect(() => serializeRule({ ...form, end: "count" })).toThrow();
		},
	);
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
