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
	},
];
examples.push(
	{
		...examples[0],
		frequency: "WEEKLY",
		weekdays: ["MO", "WE"],
		end: "until",
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
	it.each([
		["interval", Number.NaN, "Enter a whole number of 1 or more."],
		["interval", 0, "Enter a whole number of 1 or more."],
		["interval", 1.5, "Enter a whole number of 1 or more."],
		[
			"interval",
			2147483648,
			"Enter a whole number no greater than 2147483647.",
		],
		["start", "", "Enter a valid start date."],
		["start", "2026-02-30", "Enter a valid start date."],
		["time", "", "Enter a valid time."],
		["day", Number.NaN, "Enter a day between 1 and 31."],
		["month", Number.NaN, "Enter a month between 1 and 12."],
		["until", "", "Choose an end date on or after the start date."],
	] as const)(
		"uses friendly feedback for invalid %s (%s)",
		(key, value, message) => {
			const result = ruleFormSchema.safeParse({
				...examples[0],
				frequency: "YEARLY",
				end: "until",
				[key]: value,
			});
			expect(result.success).toBe(false);
			if (!result.success)
				expect(
					result.error.issues.find((issue) => issue.path[0] === key)?.message,
				).toBe(message);
		},
	);
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
	it.each(["DAILY", "WEEKLY"] as const)(
		"normalizes unused day and month for %s",
		(frequency) => {
			const form = {
				...examples[0],
				frequency,
				day: Number.NaN,
				month: Number.NaN,
			};
			expect(serializeRule(form)).not.toMatch(/BYMONTH(DAY)?=/);
			expect(ruleFormSchema.parse(form)).toMatchObject({ day: 1, month: 3 });
		},
	);
	it("validates only the day for monthly day rules and neither field for ordinal rules", () => {
		const form = {
			...examples[0],
			frequency: "MONTHLY" as const,
			month: Number.NaN,
		};
		expect(serializeRule(form)).toContain("BYMONTHDAY=1");
		expect(() => serializeRule({ ...form, day: Number.NaN })).toThrow();
		expect(
			serializeRule({ ...form, monthly: "weekday", day: Number.NaN }),
		).toContain("BYDAY=MO;BYSETPOS=1");
	});
	it.each(["day", "month"] as const)(
		"rejects a cleared active yearly %s",
		(key) => {
			expect(() =>
				serializeRule({
					...examples[0],
					frequency: "YEARLY",
					[key]: Number.NaN,
				}),
			).toThrow();
		},
	);
	it("keeps COUNT rules unsupported with a specific reason", () => {
		expect(
			parseRule("DTSTART;TZID=UTC:20260301T093000\nRRULE:FREQ=DAILY;COUNT=5"),
		).toEqual({
			supported: false,
			reason: "This rule uses COUNT, which Prefect doesn't support.",
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
	it.each(["UTC", "America/Chicago", "Asia/Kathmandu"])(
		"interprets floating starts in %s with either rule prefix",
		(timezone) => {
			for (const prefix of ["RRULE:", ""]) {
				const parsed = parseRule(
					`DTSTART:20260301T093000\n${prefix}FREQ=DAILY`,
					timezone,
				);
				expect(parsed.supported).toBe(true);
				if (parsed.supported) {
					expect(parsed.value).toMatchObject({
						start: "2026-03-01",
						time: "09:30",
						frequency: "DAILY",
					});
					const serialized = serializeRule(parsed.value, timezone);
					expect(serialized).toContain(
						`DTSTART;TZID=${timezone}:20260301T093000\nRRULE:FREQ=DAILY`,
					);
					expect(parseRule(serialized, timezone)).toEqual(parsed);
				}
			}
		},
	);
	it("accepts a bare rule line with an explicit TZID", () => {
		const start = "DTSTART;TZID=America/Chicago:20260301T093000\n";
		const parsed = parseRule(`${start}FREQ=DAILY`, "America/Chicago");
		expect(parsed.supported).toBe(true);
		expect(parsed).toEqual(
			parseRule(`${start}RRULE:FREQ=DAILY`, "America/Chicago"),
		);
	});
	it("still rejects a UTC start when the schedule timezone differs", () => {
		expect(
			parseRule("DTSTART:20260301T093000Z\nFREQ=DAILY", "America/Chicago")
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
