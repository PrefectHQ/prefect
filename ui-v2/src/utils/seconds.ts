/**
 * Parses an ISO 8601 duration string (e.g. "PT48H", "P2D") to total seconds.
 * Returns null if the string is not a valid ISO 8601 duration.
 */
function parseISO8601Duration(input: string): number | null {
	const match = input.match(
		/^P(?:(\d+)Y)?(?:(\d+)M)?(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?)?$/,
	);
	if (!match) return null;
	const [, years, months, days, hours, minutes, seconds] = match;
	return (
		Number(years ?? 0) * 31536000 +
		Number(months ?? 0) * 30 * 86400 +
		Number(days ?? 0) * 86400 +
		Number(hours ?? 0) * 3600 +
		Number(minutes ?? 0) * 60 +
		Number(seconds ?? 0)
	);
}

/**
 * Converts an interval value (numeric seconds or ISO 8601 duration string) to seconds.
 */
export function intervalToSeconds(interval: number | string): number {
	if (typeof interval === "number") return interval;
	const parsed = parseISO8601Duration(interval);
	if (parsed !== null) return parsed;
	const num = Number(interval);
	if (!Number.isNaN(num)) return num;
	return 0;
}

/**
 * Time interval constants in seconds
 */
export const intervals = {
	year: 31536000,
	day: 86400,
	hour: 3600,
	minute: 60,
	second: 1,
} as const;

type IntervalTypes = keyof typeof intervals;
type IntervalTypesShort = "y" | "d" | "h" | "m" | "s";
type IntervalTypesPlural = `${keyof typeof intervals}s`;

function aggregateSeconds(input: number): Record<IntervalTypesPlural, number> {
	const years = Math.floor(input / intervals.year);
	const days = Math.floor((input % intervals.year) / intervals.day);
	const hours = Math.floor(
		((input % intervals.year) % intervals.day) / intervals.hour,
	);
	const minutes = Math.floor(
		(((input % intervals.year) % intervals.day) % intervals.hour) /
			intervals.minute,
	);
	const seconds = Math.ceil(
		(((input % intervals.year) % intervals.day) % intervals.hour) %
			intervals.minute,
	);

	return { years, days, hours, minutes, seconds };
}

function intervalStringSeconds(seconds: number, showOnes = true): string {
	return `${seconds === 1 && !showOnes ? "" : seconds}`;
}

function intervalStringIntervalType(
	type: IntervalTypes,
	seconds: number,
	showOnes = true,
): string {
	return `${intervalStringSeconds(seconds, showOnes)} ${type}${seconds !== 1 ? "s" : ""}`;
}

function intervalStringSecondsIntervalTypeShort(
	type: IntervalTypesShort,
	seconds: number,
	showOnes = true,
): string {
	return `${intervalStringSeconds(seconds, showOnes)}${type}`;
}

/**
 * Converts seconds to a human-readable string with full interval names
 * @example secondsToString(3661) // "1 hour 1 minute 1 second"
 */
export function secondsToString(input: number, showOnes = true): string {
	const { years, days, hours, minutes, seconds } = aggregateSeconds(input);
	const year = years ? intervalStringIntervalType("year", years, showOnes) : "";
	const day = days ? intervalStringIntervalType("day", days, showOnes) : "";
	const hour = hours ? intervalStringIntervalType("hour", hours, showOnes) : "";
	const minute = minutes
		? intervalStringIntervalType("minute", minutes, showOnes)
		: "";
	const second = seconds
		? intervalStringIntervalType("second", seconds, showOnes)
		: "";

	return [year, day, hour, minute, second]
		.map((x) => (x ? x : ""))
		.join(" ")
		.trim();
}

/**
 * Converts seconds to a compact, approximate human-readable string
 * Shows only the most significant time units for brevity
 * @example secondsToApproximateString(3661) // "1h 1m"
 * @example secondsToApproximateString(25) // "25s"
 * @example secondsToApproximateString(90061) // "1d 1h"
 */
export function secondsToApproximateString(
	input: number,
	showOnes = true,
): string {
	const { years, days, hours, minutes, seconds } = aggregateSeconds(input);
	const year = intervalStringSecondsIntervalTypeShort("y", years, showOnes);
	const day = intervalStringSecondsIntervalTypeShort("d", days, showOnes);
	const hour = intervalStringSecondsIntervalTypeShort("h", hours, showOnes);
	const minute = intervalStringSecondsIntervalTypeShort("m", minutes, showOnes);
	const second = intervalStringSecondsIntervalTypeShort("s", seconds, showOnes);

	switch (true) {
		case years > 0 && days === 0:
			return year;
		case years > 0 && days > 0:
			return `${year} ${day}`;
		case days > 0 && hours === 0:
			return day;
		case days > 0 && hours > 0:
			return `${day} ${hour}`;
		case hours > 0 && minutes === 0:
			return `${hour} ${minute}`;
		case hours > 0 && minutes > 0:
			return `${hour} ${minute}`;
		case minutes > 0 && seconds === 0:
			return minute;
		case minutes > 0 && seconds > 0:
			return `${minute} ${second}`;
		default:
			return second;
	}
}
