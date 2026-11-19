import { RRule, rrulestr } from "rrule";
import { z } from "zod";

export const weekdays = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"] as const;
export type Weekday = (typeof weekdays)[number];
export const frequencies = ["DAILY", "WEEKLY", "MONTHLY", "YEARLY"] as const;
export const dayNames = [
	"Monday",
	"Tuesday",
	"Wednesday",
	"Thursday",
	"Friday",
	"Saturday",
	"Sunday",
];
export type RuleForm = {
	frequency: (typeof frequencies)[number];
	interval: number;
	start: string;
	time: string;
	weekdays: Weekday[];
	monthly: "day" | "weekday";
	day: number;
	month: number;
	position: number;
	weekday: Weekday;
	end: "never" | "until";
	until: string;
};
export type ParsedRule =
	| { supported: true; value: RuleForm }
	| { supported: false; reason: string };

const integer = (value: number, min: number, max: number) =>
	Number.isInteger(value) && value >= min && value <= max;
const validDate = (value: string) =>
	/^\d{4}-\d{2}-\d{2}$/.test(value) &&
	!value.startsWith("0000-") &&
	Number.isFinite(Date.parse(value)) &&
	new Date(value).toISOString().slice(0, 10) === value;
const stamp = (date: string, time: string) =>
	`${date.replaceAll("-", "")}T${time.replace(":", "")}00`;
const serverUntilStamp = (date: string) =>
	`${date.replaceAll("-", "")}T235959Z`;

export const ruleFormSchema = z
	.object({
		frequency: z.enum(frequencies),
		interval: z
			.number({ error: "Enter a whole number of 1 or more." })
			.int({ error: "Enter a whole number of 1 or more." })
			.min(1, { error: "Enter a whole number of 1 or more." })
			.max(2147483647, {
				error: "Enter a whole number no greater than 2147483647.",
			}),
		start: z
			.string()
			.refine(validDate, { message: "Enter a valid start date." }),
		time: z
			.string()
			.regex(/^([01]\d|2[0-3]):[0-5]\d$/, { message: "Enter a valid time." }),
		weekdays: z.array(z.enum(weekdays)),
		monthly: z.enum(["day", "weekday"]),
		day: z.union([z.number(), z.nan()]),
		month: z.union([z.number(), z.nan()]),
		position: z.number().refine((value) => [1, 2, 3, 4, 5, -1].includes(value)),
		weekday: z.enum(weekdays),
		end: z.enum(["never", "until"]),
		until: z.string(),
	})
	.refine(
		(value) => value.frequency !== "WEEKLY" || value.weekdays.length > 0,
		{ path: ["weekdays"], message: "Select at least one weekday." },
	)
	.refine(
		(value) =>
			(value.frequency !== "YEARLY" &&
				(value.frequency !== "MONTHLY" || value.monthly !== "day")) ||
			integer(value.day, 1, 31),
		{
			path: ["day"],
			message: "Enter a day between 1 and 31.",
		},
	)
	.refine(
		(value) => value.frequency !== "YEARLY" || integer(value.month, 1, 12),
		{
			path: ["month"],
			message: "Enter a month between 1 and 12.",
		},
	)
	.refine(
		(value) =>
			value.end !== "until" ||
			(validDate(value.until) && value.until >= value.start),
		{
			path: ["until"],
			message: "Choose an end date on or after the start date.",
		},
	)
	.refine(
		(value) =>
			value.frequency !== "YEARLY" ||
			value.day <= new Date(Date.UTC(2000, value.month, 0)).getUTCDate(),
		{ path: ["day"], message: "Choose a valid day for this month." },
	)
	.transform((value) => ({
		...value,
		day:
			value.frequency === "YEARLY" ||
			(value.frequency === "MONTHLY" && value.monthly === "day")
				? value.day
				: new Date(`${value.start}T00:00:00Z`).getUTCDate(),
		month:
			value.frequency === "YEARLY"
				? value.month
				: new Date(`${value.start}T00:00:00Z`).getUTCMonth() + 1,
	}));

export function serializeRule(form: RuleForm, timezone = "UTC"): string {
	new Intl.DateTimeFormat("en", { timeZone: timezone });
	const value = ruleFormSchema.parse(form);
	const [hour, minute] = value.time.split(":").map(Number);
	const parts = [`FREQ=${value.frequency}`, `INTERVAL=${value.interval}`];
	if (value.frequency === "WEEKLY")
		parts.push(
			`BYDAY=${weekdays.filter((day) => value.weekdays.includes(day)).join(",")}`,
		);
	if (value.frequency === "MONTHLY") {
		if (value.monthly === "day") parts.push(`BYMONTHDAY=${value.day}`);
		else parts.push(`BYDAY=${value.weekday}`, `BYSETPOS=${value.position}`);
	}
	if (value.frequency === "YEARLY")
		parts.push(`BYMONTH=${value.month}`, `BYMONTHDAY=${value.day}`);
	parts.push(`BYHOUR=${hour}`, `BYMINUTE=${minute}`, "BYSECOND=0");
	if (value.end === "until")
		parts.push(`UNTIL=${serverUntilStamp(value.until)}`);
	return `DTSTART;TZID=${timezone}:${stamp(value.start, value.time)}\nRRULE:${parts.join(";")}`;
}

export function parseRule(rule: string, timezone = "UTC"): ParsedRule {
	const unsupported = (reason: string): ParsedRule => ({
		supported: false,
		reason,
	});
	try {
		const lines = rule.trim().split(/\r?\n/);
		if (lines.length !== 2)
			return unsupported(
				"The builder requires one DTSTART and one RRULE, without additional rules or dates.",
			);
		const startMatch =
			/^DTSTART(?:;TZID=([^:]+))?:(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})(Z?)$/.exec(
				lines[0],
			);
		if (!startMatch) return unsupported("A complete DTSTART is required.");
		const [, tzid, year, month, day, hour, minute, second, zulu] = startMatch;
		if (
			(tzid ?? (zulu ? "UTC" : timezone)) !== timezone ||
			(tzid && zulu) ||
			second !== "00"
		)
			return unsupported(
				"The start timezone or seconds cannot be represented by this builder.",
			);
		const fields: Record<string, string> = {};
		const allowed = [
			"FREQ",
			"INTERVAL",
			"BYDAY",
			"BYMONTHDAY",
			"BYMONTH",
			"BYSETPOS",
			"BYHOUR",
			"BYMINUTE",
			"BYSECOND",
			"COUNT",
			"UNTIL",
		];
		const ruleLine = /^RRULE:/i.test(lines[1]) ? lines[1].slice(6) : lines[1];
		for (const part of ruleLine.split(";")) {
			const [key, value, extra] = part.split("=");
			if (!allowed.includes(key) || !value || extra || key in fields)
				return unsupported(
					"This rule contains unsupported or duplicate fields.",
				);
			fields[key] = value;
		}
		if (fields.COUNT)
			return unsupported(
				"This rule uses COUNT, which Prefect doesn't support.",
			);
		const frequency = frequencies.find((item) => item === fields.FREQ);
		if (!frequency)
			return unsupported(
				"Only daily, weekly, monthly and yearly rules are supported.",
			);
		const start = `${year}-${month}-${day}`;
		const value: RuleForm = {
			frequency,
			interval: Number(fields.INTERVAL ?? 1),
			start,
			time: `${String(Number(fields.BYHOUR ?? hour)).padStart(2, "0")}:${String(Number(fields.BYMINUTE ?? minute)).padStart(2, "0")}`,
			weekdays: [
				weekdays[(new Date(`${start}T00:00:00Z`).getUTCDay() + 6) % 7],
			],
			monthly: "day",
			day: Number(fields.BYMONTHDAY ?? day),
			month: Number(fields.BYMONTH ?? month),
			position: 1,
			weekday: "MO",
			end: fields.UNTIL ? "until" : "never",
			until: start,
		};
		if (
			(fields.BYSECOND && fields.BYSECOND !== "0") ||
			value.time !== `${hour}:${minute}`
		)
			return unsupported(
				"Multiple times or a start time different from the recurrence time are not supported.",
			);
		if (frequency === "YEARLY" && fields.BYMONTHDAY && !fields.BYMONTH)
			return unsupported(
				"Yearly day-of-month filters require an explicit month.",
			);
		if (fields.BYMONTH && frequency !== "YEARLY")
			return unsupported("Month filters are only supported for yearly rules.");
		if (fields.BYMONTHDAY && frequency !== "MONTHLY" && frequency !== "YEARLY")
			return unsupported(
				"Day-of-month filters are not supported for this frequency.",
			);
		if (fields.BYSETPOS && (frequency !== "MONTHLY" || !fields.BYDAY))
			return unsupported("Set positions require a monthly weekday.");
		if (fields.BYDAY) {
			if (frequency === "WEEKLY") {
				const days = fields.BYDAY.split(",");
				if (
					!days.every((item): item is Weekday =>
						weekdays.some((weekday) => weekday === item),
					)
				)
					return unsupported(
						"Only plain weekdays are supported for weekly rules.",
					);
				value.weekdays = days;
			} else if (frequency === "MONTHLY" && !fields.BYMONTHDAY) {
				const match = /^(-1|[1-5])?(MO|TU|WE|TH|FR|SA|SU)$/.exec(fields.BYDAY);
				const weekday = weekdays.find((item) => item === match?.[2]);
				if (
					!match ||
					!weekday ||
					(!match[1] && !fields.BYSETPOS) ||
					(match[1] && fields.BYSETPOS)
				)
					return unsupported("Choose one ordinal weekday per month.");
				value.monthly = "weekday";
				value.weekday = weekday;
				value.position = Number(match[1] ?? fields.BYSETPOS);
			} else
				return unsupported(
					"Weekday filters cannot be represented for this frequency.",
				);
		}
		if (fields.UNTIL) {
			if (!/^\d{8}T\d{6}Z$/.test(fields.UNTIL))
				return unsupported(
					"UNTIL must be a Z-suffixed local end-of-day timestamp.",
				);
			const until = RRule.parseString(`FREQ=DAILY;UNTIL=${fields.UNTIL}`).until;
			if (!until) return unsupported("Invalid end date.");
			value.until = until.toISOString().slice(0, 10);
			if (serverUntilStamp(value.until) !== fields.UNTIL)
				return unsupported(
					"Only end-of-day UNTIL values can be edited in the builder.",
				);
		}
		serializeRule(value, timezone);
		rrulestr(rule);
		return { supported: true, value };
	} catch {
		return unsupported(
			"This rule is invalid or cannot be represented by the builder.",
		);
	}
}

export function describeRule(rule: string): string {
	try {
		const parsed = rrulestr(rule);
		return parsed instanceof RRule ? parsed.toText() || rule : rule;
	} catch {
		return rule;
	}
}

type MonthlySettings = Pick<
	RuleForm,
	"monthly" | "day" | "position" | "weekday"
>;
const ordinalNames: Record<number, string> = {
	1: "first",
	2: "second",
	3: "third",
	4: "fourth",
	5: "fifth",
	[-1]: "last",
};
function monthlyOption(settings: MonthlySettings) {
	return {
		value:
			settings.monthly === "day"
				? `day:${settings.day}`
				: `weekday:${settings.position}:${settings.weekday}`,
		label:
			settings.monthly === "day"
				? `Monthly on day ${settings.day}`
				: `Monthly on the ${ordinalNames[settings.position]} ${dayNames[weekdays.indexOf(settings.weekday)]}`,
		settings,
	};
}

export function getMonthlyOptions(value: RuleForm) {
	const options = [];
	if (validDate(value.start)) {
		const date = new Date(`${value.start}T00:00:00Z`);
		const day = date.getUTCDate();
		const weekday = weekdays[(date.getUTCDay() + 6) % 7];
		options.push(monthlyOption({ ...value, monthly: "day", day }));
		options.push(
			monthlyOption({
				...value,
				monthly: "weekday",
				position: Math.ceil(day / 7),
				weekday,
			}),
		);
		const daysInMonth = new Date(
			Date.UTC(date.getUTCFullYear(), date.getUTCMonth() + 1, 0),
		).getUTCDate();
		if (day + 7 > daysInMonth)
			options.push(
				monthlyOption({ ...value, monthly: "weekday", position: -1, weekday }),
			);
	}
	const current = monthlyOption(value);
	if (!options.some((option) => option.value === current.value))
		options.push(current);
	return { options, selected: current.value };
}

export function getAnnualLabel(value: RuleForm): string | null {
	if (!validDate(value.start)) return null;
	const date = new Date(`${value.start}T00:00:00Z`);
	if (date.getUTCMonth() + 1 !== value.month || date.getUTCDate() !== value.day)
		return null;
	return `Annually on ${new Intl.DateTimeFormat("en-US", { month: "long", day: "numeric", timeZone: "UTC" }).format(date)}`;
}
