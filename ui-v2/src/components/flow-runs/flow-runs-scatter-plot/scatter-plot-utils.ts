/**
 * Utility functions for scatter plot axis formatting and tick generation.
 * These are separated from the component to avoid React Fast Refresh warnings.
 */

/**
 * Formats a duration value (in seconds) to a compact string representation.
 * Examples: "0s", "0.50s", "30s", "5m", "2h", "3d", "1y"
 */
export const formatYAxisTick = (value: number): string => {
	if (value === 0) return "0s";
	if (value < 1) return `${value.toFixed(2)}s`;

	const SECONDS_PER_YEAR = 31536000;
	const SECONDS_PER_DAY = 86400;
	const SECONDS_PER_HOUR = 3600;
	const SECONDS_PER_MINUTE = 60;

	const years = Math.floor(value / SECONDS_PER_YEAR);
	if (years > 0) return `${years}y`;

	const days = Math.floor(value / SECONDS_PER_DAY);
	if (days > 0) return `${days}d`;

	const hours = Math.floor(value / SECONDS_PER_HOUR);
	if (hours > 0) return `${hours}h`;

	const minutes = Math.floor(value / SECONDS_PER_MINUTE);
	if (minutes > 0) return `${minutes}m`;

	return `${Math.ceil(value)}s`;
};

/**
 * Standard time intervals for generating "nice" tick values.
 * Similar to D3's time scale tick generation.
 */
export const TIME_INTERVALS = [
	{ ms: 1000, name: "second" },
	{ ms: 5 * 1000, name: "5seconds" },
	{ ms: 15 * 1000, name: "15seconds" },
	{ ms: 30 * 1000, name: "30seconds" },
	{ ms: 60 * 1000, name: "minute" },
	{ ms: 5 * 60 * 1000, name: "5minutes" },
	{ ms: 15 * 60 * 1000, name: "15minutes" },
	{ ms: 30 * 60 * 1000, name: "30minutes" },
	{ ms: 60 * 60 * 1000, name: "hour" },
	{ ms: 3 * 60 * 60 * 1000, name: "3hours" },
	{ ms: 6 * 60 * 60 * 1000, name: "6hours" },
	{ ms: 12 * 60 * 60 * 1000, name: "12hours" },
	{ ms: 24 * 60 * 60 * 1000, name: "day" },
	{ ms: 2 * 24 * 60 * 60 * 1000, name: "2days" },
	{ ms: 3 * 24 * 60 * 60 * 1000, name: "3days" },
	{ ms: 7 * 24 * 60 * 60 * 1000, name: "week" },
	{ ms: 30 * 24 * 60 * 60 * 1000, name: "month" },
];

const HOUR_MS = 60 * 60 * 1000;
const DAY_MS = 24 * HOUR_MS;
const MONTH_MS = 30 * DAY_MS;

/**
 * Generates ticks for intervals of an hour or more on local time boundaries:
 * local midnight for day intervals, the first of the month for the month
 * interval, and local hours divisible by the step for hour intervals.
 */
const generateLocalTimeTicks = (
	startMs: number,
	endMs: number,
	intervalMs: number,
): number[] => {
	const ticks: number[] = [];
	const cursor = new Date(startMs);

	if (intervalMs >= MONTH_MS) {
		cursor.setDate(1);
		cursor.setHours(0, 0, 0, 0);
		if (cursor.getTime() < startMs) cursor.setMonth(cursor.getMonth() + 1);
		while (cursor.getTime() <= endMs) {
			ticks.push(cursor.getTime());
			cursor.setMonth(cursor.getMonth() + 1);
		}
		return ticks;
	}

	if (intervalMs >= DAY_MS) {
		const stepDays = Math.round(intervalMs / DAY_MS);
		cursor.setHours(0, 0, 0, 0);
		if (cursor.getTime() < startMs) cursor.setDate(cursor.getDate() + 1);
		while (cursor.getTime() <= endMs) {
			ticks.push(cursor.getTime());
			cursor.setDate(cursor.getDate() + stepDays);
		}
		return ticks;
	}

	const stepHours = Math.round(intervalMs / HOUR_MS);
	cursor.setMinutes(0, 0, 0);
	if (cursor.getTime() < startMs) cursor.setHours(cursor.getHours() + 1);
	while (cursor.getTime() <= endMs) {
		if (cursor.getHours() % stepHours === 0) ticks.push(cursor.getTime());
		cursor.setHours(cursor.getHours() + 1);
	}
	return ticks;
};

/**
 * Generates tick values aligned with "nice" time boundaries.
 * Similar to D3's time scale tick generation, this ensures ticks fall on
 * natural boundaries like hour marks, day boundaries, etc.
 *
 * Intervals of an hour or more are aligned in local time. Multiples of the
 * interval since the epoch put day ticks on UTC midnight, which is not a day
 * boundary in most timezones, so every tick would be labelled with the same
 * hour instead of a date.
 */
export const generateNiceTimeTicks = (
	startMs: number,
	endMs: number,
	targetTickCount: number,
): number[] => {
	const range = endMs - startMs;
	if (range <= 0) return [startMs];

	const idealInterval = range / targetTickCount;
	let chosenInterval = TIME_INTERVALS[0].ms;
	for (const interval of TIME_INTERVALS) {
		if (interval.ms >= idealInterval) {
			chosenInterval = interval.ms;
			break;
		}
		chosenInterval = interval.ms;
	}

	const ticks: number[] = [];
	if (chosenInterval >= HOUR_MS) {
		ticks.push(...generateLocalTimeTicks(startMs, endMs, chosenInterval));
	} else {
		const firstTick = Math.ceil(startMs / chosenInterval) * chosenInterval;
		for (let tick = firstTick; tick <= endMs; tick += chosenInterval) {
			ticks.push(tick);
		}
	}

	if (ticks.length === 0) {
		ticks.push(startMs);
	}

	return ticks;
};

/**
 * Creates a formatter for X-axis tick labels based on time boundaries.
 * Uses V1's hierarchical approach: checks which time boundary the timestamp
 * crosses (millisecond, second, minute, hour, day, month, year) and formats accordingly.
 */
export const createXAxisTickFormatter = () => {
	return (value: number): string => {
		const date = new Date(value);

		const second = new Date(date);
		second.setMilliseconds(0);
		if (second.getTime() < date.getTime()) {
			return `.${date.getMilliseconds().toString().padStart(3, "0").slice(0, 3)}`;
		}

		const minute = new Date(date);
		minute.setSeconds(0, 0);
		if (minute.getTime() < date.getTime()) {
			return `:${date.getSeconds().toString().padStart(2, "0")}`;
		}

		const hour = new Date(date);
		hour.setMinutes(0, 0, 0);
		if (hour.getTime() < date.getTime()) {
			return date.toLocaleTimeString(undefined, {
				hour: "numeric",
				minute: "2-digit",
			});
		}

		const day = new Date(date);
		day.setHours(0, 0, 0, 0);
		if (day.getTime() < date.getTime()) {
			return date.toLocaleTimeString(undefined, {
				hour: "numeric",
				hour12: true,
			});
		}

		const month = new Date(date);
		month.setDate(1);
		month.setHours(0, 0, 0, 0);
		if (month.getTime() < date.getTime()) {
			return date.toLocaleDateString(undefined, {
				weekday: "short",
				day: "numeric",
			});
		}

		const year = new Date(date);
		year.setMonth(0, 1);
		year.setHours(0, 0, 0, 0);
		if (year.getTime() < date.getTime()) {
			return date.toLocaleDateString(undefined, { month: "long" });
		}

		return date.getFullYear().toString();
	};
};
