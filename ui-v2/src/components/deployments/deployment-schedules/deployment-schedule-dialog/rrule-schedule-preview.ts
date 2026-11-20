import { RRule } from "rrule";
import { parseRule, serializeRule } from "@/components/ui/rrule-builder";
import { weekdays } from "@/components/ui/rrule-builder/utils";

const DAY = 86400000;
const MAX_PERIODS = 1000;
export type RRulePreview =
	| { status: "ready"; dates: Date[] }
	| { status: "unsupported" | "error" };

function calendarDate(year: number, month: number, day = 1) {
	const date = new Date(0);
	date.setUTCFullYear(year, month, day);
	return date;
}

function wallClock(date: Date, formatter: Intl.DateTimeFormat) {
	const parts = Object.fromEntries(
		formatter.formatToParts(date).map(({ type, value }) => [type, value]),
	);
	const result = calendarDate(
		Number(parts.year),
		Number(parts.month) - 1,
		Number(parts.day),
	);
	result.setUTCHours(
		Number(parts.hour),
		Number(parts.minute),
		Number(parts.second),
	);
	return result.getTime();
}

// dateutil chooses the first fold and the post-transition offset for a gap.
function resolveWallClock(wall: Date, formatter: Intl.DateTimeFormat) {
	const stamp = wall.getTime();
	const offsets = [-2, -1, 0, 1, 2].map((days) => {
		const probe = stamp + days * DAY;
		return wallClock(new Date(probe), formatter) - probe;
	});
	const candidates = [...new Set(offsets)].map((offset) => stamp - offset);
	const matching = candidates.filter(
		(instant) => wallClock(new Date(instant), formatter) === stamp,
	);
	return new Date(
		matching.length
			? Math.min(...matching)
			: stamp - offsets[offsets.length - 1],
	);
}

export function previewRRule(
	rule: string,
	timezone: string,
	now = new Date(),
): RRulePreview {
	const parsed = parseRule(rule, timezone);
	if (!parsed.supported) return { status: "unsupported" };
	try {
		const formatter = new Intl.DateTimeFormat("en-GB", {
			timeZone: timezone,
			year: "numeric",
			month: "2-digit",
			day: "2-digit",
			hour: "2-digit",
			minute: "2-digit",
			second: "2-digit",
			hourCycle: "h23",
		});
		const { value } = parsed;
		const anchor = new Date(`${value.start}T${value.time}:00Z`);
		const lower = new Date(wallClock(now, formatter) - 2 * DAY);
		const options = RRule.parseString(
			serializeRule(value, timezone).split("\n")[1],
		);
		const until = options.until?.getTime() ?? Number.POSITIVE_INFINITY;
		const year = anchor.getUTCFullYear();
		const month = anchor.getUTCMonth();
		const day = anchor.getUTCDate();
		const weekly = value.frequency === "WEEKLY";
		const origin = calendarDate(
			year,
			month,
			day - (weekly ? (anchor.getUTCDay() + 6) % 7 : 0),
		);
		const period = (index: number) => {
			const step = index * value.interval;
			if (value.frequency === "YEARLY") return calendarDate(year + step, 0);
			if (value.frequency === "MONTHLY")
				return calendarDate(year, month + step);
			return new Date(origin.getTime() + step * (weekly ? 7 : 1) * DAY);
		};
		const distance =
			value.frequency === "YEARLY"
				? lower.getUTCFullYear() - year
				: value.frequency === "MONTHLY"
					? (lower.getUTCFullYear() - year) * 12 + lower.getUTCMonth() - month
					: (lower.getTime() - origin.getTime()) / ((weekly ? 7 : 1) * DAY);
		const first = Math.max(0, Math.floor(distance / value.interval));
		const dates = new Map<number, Date>();
		let candidates = 0;
		for (let attempt = 0; attempt < MAX_PERIODS; attempt++) {
			const index = first + attempt;
			const start = period(index);
			if (start.getUTCFullYear() > 9999 || start.getTime() > until)
				return {
					status: "ready",
					dates: [...dates.values()]
						.sort((a, b) => a.getTime() - b.getTime())
						.slice(0, 5),
				};
			// Enumerate days without filters: rrule otherwise scans to year 9999 for impossible patterns.
			const end =
				value.frequency === "YEARLY"
					? calendarDate(start.getUTCFullYear() + 1, 0)
					: value.frequency === "MONTHLY"
						? calendarDate(start.getUTCFullYear(), start.getUTCMonth() + 1)
						: new Date(start.getTime() + (weekly ? 7 : 1) * DAY);
			const bounded = new RRule({
				freq: RRule.DAILY,
				byhour: anchor.getUTCHours(),
				byminute: anchor.getUTCMinutes(),
				bysecond: 0,
				dtstart: new Date(Math.max(anchor.getTime(), start.getTime())),
				until: new Date(Math.min(until, end.getTime() - 1)),
			});
			for (const wall of bounded.all()) {
				if (++candidates > 10000) return { status: "error" };
				const weekday = weekdays[(wall.getUTCDay() + 6) % 7];
				const monthDay = wall.getUTCDate();
				if (weekly && !value.weekdays.includes(weekday)) continue;
				if (
					value.frequency === "YEARLY" &&
					(wall.getUTCMonth() + 1 !== value.month || monthDay !== value.day)
				)
					continue;
				if (value.frequency === "MONTHLY") {
					if (value.monthly === "day" && monthDay !== value.day) continue;
					if (
						value.monthly === "weekday" &&
						(weekday !== value.weekday ||
							(value.position === -1
								? monthDay + 7 <=
									calendarDate(
										wall.getUTCFullYear(),
										wall.getUTCMonth() + 1,
										0,
									).getUTCDate()
								: Math.ceil(monthDay / 7) !== value.position))
					)
						continue;
				}
				const instant = resolveWallClock(wall, formatter);
				if (instant >= now) dates.set(instant.getTime(), instant);
			}
			if (dates.size >= 5)
				return {
					status: "ready",
					dates: [...dates.values()]
						.sort((a, b) => a.getTime() - b.getTime())
						.slice(0, 5),
				};
		}
		return { status: "error" };
	} catch {
		return { status: "error" };
	}
}
