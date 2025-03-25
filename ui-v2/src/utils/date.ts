import { format } from "date-fns";

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
