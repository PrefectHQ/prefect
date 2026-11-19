import { formatInTimeZone, fromZonedTime } from "date-fns-tz";
import { RRule, rrulestr } from "rrule";
import { z } from "zod";

export const weekdays = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"] as const;
export type Weekday = (typeof weekdays)[number];
export const frequencies = ["DAILY", "WEEKLY", "MONTHLY", "YEARLY"] as const;
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
	end: "never" | "until" | "count";
	until: string;
	count: number;
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
const untilInstant = (date: string, timezone: string) =>
	fromZonedTime(`${date}T23:59:59`, timezone);
const utcStamp = (date: Date) =>
	date.toISOString().replaceAll(/[-:]/g, "").replace(".000", "");

export const ruleFormSchema = z
	.object({
		frequency: z.enum(frequencies),
		interval: z.number().int().min(1).max(2147483647),
		start: z.string().refine(validDate),
		time: z.string().regex(/^([01]\d|2[0-3]):[0-5]\d$/),
		weekdays: z.array(z.enum(weekdays)),
		monthly: z.enum(["day", "weekday"]),
		day: z.number().int().min(1).max(31),
		month: z.number().int().min(1).max(12),
		position: z.number().refine((value) => [1, 2, 3, 4, 5, -1].includes(value)),
		weekday: z.enum(weekdays),
		end: z.enum(["never", "until", "count"]),
		until: z.string(),
		count: z.number(),
	})
	.refine((value) => value.frequency !== "WEEKLY" || value.weekdays.length > 0)
	.refine(
		(value) => value.end !== "count" || integer(value.count, 1, 2147483647),
	)
	.refine(
		(value) =>
			value.end !== "until" ||
			(validDate(value.until) && value.until >= value.start),
	)
	.refine(
		(value) =>
			value.frequency !== "YEARLY" ||
			value.day <= new Date(Date.UTC(2000, value.month, 0)).getUTCDate(),
	);

export function serializeRule(value: RuleForm, timezone = "UTC"): string {
	new Intl.DateTimeFormat("en", { timeZone: timezone });
	ruleFormSchema.parse(value);
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
	if (value.end === "count") parts.push(`COUNT=${value.count}`);
	if (value.end === "until")
		parts.push(`UNTIL=${utcStamp(untilInstant(value.until, timezone))}`);
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
		if (!startMatch || !lines[1].startsWith("RRULE:"))
			return unsupported("A complete DTSTART is required.");
		const [, tzid, year, month, day, hour, minute, second, zulu] = startMatch;
		if (
			(tzid ?? (zulu ? "UTC" : timezone)) !== timezone ||
			(!tzid && !zulu && timezone !== "UTC") ||
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
		for (const part of lines[1].slice(6).split(";")) {
			const [key, value, extra] = part.split("=");
			if (!allowed.includes(key) || !value || extra || key in fields)
				return unsupported(
					"This rule contains unsupported or duplicate fields.",
				);
			fields[key] = value;
		}
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
			end: fields.COUNT ? "count" : fields.UNTIL ? "until" : "never",
			count: Number(fields.COUNT ?? 10),
			until: start,
		};
		if (
			(fields.BYSECOND && fields.BYSECOND !== "0") ||
			value.time !== `${hour}:${minute}`
		)
			return unsupported(
				"Multiple times or a start time different from the recurrence time are not supported.",
			);
		if (fields.COUNT && fields.UNTIL)
			return unsupported("COUNT and UNTIL cannot be combined.");
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
				return unsupported("UNTIL must be a UTC end-of-day timestamp.");
			const until = RRule.parseString(`FREQ=DAILY;UNTIL=${fields.UNTIL}`).until;
			if (!until) return unsupported("Invalid end date.");
			value.until = formatInTimeZone(until, timezone, "yyyy-MM-dd");
			if (utcStamp(untilInstant(value.until, timezone)) !== fields.UNTIL)
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
