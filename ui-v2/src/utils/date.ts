import { differenceInSeconds, format, isBefore } from "date-fns";

import { secondsToApproximateString } from "./seconds";

const dateFormat = "MMM do, yyyy";
const timeFormat = "hh:mm a";
const dateTimeFormat = `${dateFormat} 'at' ${timeFormat}`;

const timeNumericFormat = "hh:mm:ss a";
const timeNumericShortFormat = "hh:mm a";
const dateNumericFormat = "yyyy/MM/dd";
const dateTimeNumericFormat = `${dateNumericFormat} ${timeNumericFormat}`;
const dateTimeNumericShortFormat = `${dateNumericFormat} ${timeNumericShortFormat}`;

export const dateFormats = {
	date: dateFormat,
	time: timeFormat,
	dateTime: dateTimeFormat,
	timeNumeric: timeNumericFormat,
	timeNumericShort: timeNumericShortFormat,
	dateNumeric: dateNumericFormat,
	dateTimeNumeric: dateTimeNumericFormat,
	dateTimeNumericShort: dateTimeNumericShortFormat,
} as const;

type DateFormat = keyof typeof dateFormats;

function toDate(value: Date | string): Date {
	return new Date(value);
}

export function formatDate(
	value: Date | string,
	type: DateFormat = "date",
): string {
	const date = toDate(value);

	return format(date, dateFormats[type]);
}

/**
 * Formats a date as a relative time string (e.g., "25s ago" or "in 5m")
 * Uses compact format from secondsToApproximateString
 * @param value - The date to format
 * @param comparedTo - The date to compare against (defaults to now)
 * @returns A compact relative time string like "25s ago" or "in 5m"
 */
export function formatDateTimeRelative(
	value: Date | string,
	comparedTo: Date | string = new Date(),
): string {
	const valueDate = toDate(value);
	const compareDate = toDate(comparedTo);
	const seconds = differenceInSeconds(compareDate, valueDate);
	const past = isBefore(valueDate, compareDate);
	const formatted = secondsToApproximateString(Math.abs(seconds));

	if (past) {
		return `${formatted} ago`;
	}

	return `in ${formatted}`;
}
