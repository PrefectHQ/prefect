import {
	addSeconds,
	differenceInSeconds,
	endOfToday,
	startOfToday,
	subSeconds,
} from "date-fns";
import {
	secondsInDay,
	secondsInHour,
	secondsInMinute,
} from "date-fns/constants";
import type {
	DateRangeSelectAroundUnit,
	DateRangeSelectValue,
} from "./rich-date-range-selector";

// Map DateRangeSelectValue to concrete start/end and a span length for prev/next stepping
export type DateRangeWithTimeSpan = {
	startDate: Date;
	endDate: Date;
	timeSpanInSeconds: number;
};

function nowWithoutMilliseconds(): Date {
	const d = new Date();
	d.setMilliseconds(0);
	return d;
}

export function getMultiplierForUnit(unit: DateRangeSelectAroundUnit): number {
	switch (unit) {
		case "second":
			return 1;
		case "minute":
			return secondsInMinute;
		case "hour":
			return secondsInHour;
		case "day":
			return secondsInDay;
	}
}

/**
 * Maps a DateRangeSelectValue to concrete start/end dates and a time span.
 * This is the canonical function for converting any date range value to actual dates.
 */
export function mapValueToRange(
	source: DateRangeSelectValue,
): DateRangeWithTimeSpan | null {
	if (!source) return null;
	switch (source.type) {
		case "range": {
			const timeSpanInSeconds = differenceInSeconds(
				source.endDate,
				source.startDate,
			);
			return {
				startDate: source.startDate,
				endDate: source.endDate,
				timeSpanInSeconds,
			};
		}
		case "span": {
			const now = nowWithoutMilliseconds();
			const then = addSeconds(now, source.seconds);
			const [startDate, endDate] = [now, then].sort(
				(a, b) => a.getTime() - b.getTime(),
			);
			const timeSpanInSeconds = Math.abs(source.seconds);
			return { startDate, endDate, timeSpanInSeconds };
		}
		case "around": {
			const seconds = Math.abs(
				source.quantity * getMultiplierForUnit(source.unit),
			);
			const startDate = subSeconds(source.date, seconds);
			const endDate = addSeconds(source.date, seconds);
			const timeSpanInSeconds = differenceInSeconds(endDate, startDate);
			return { startDate, endDate, timeSpanInSeconds };
		}
		case "period": {
			// Only Today supported currently
			const startDate = startOfToday();
			const endDate = endOfToday();
			const timeSpanInSeconds = differenceInSeconds(endDate, startDate);
			return { startDate, endDate, timeSpanInSeconds };
		}
		default:
			return null;
	}
}
