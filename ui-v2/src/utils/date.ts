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

const intervals = {
	year: 31536000,
	day: 86400,
	hour: 3600,
	minute: 60,
	second: 1,
} as const;

type IntervalTypes = keyof typeof intervals;
type IntervalTypesShort = "y" | "d" | "h" | "m" | "s";

function aggregateSeconds(input: number): Record<`${IntervalTypes}s`, number> {
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

function intervalStringSecondsIntervalTypeShort(
	type: IntervalTypesShort,
	seconds: number,
	showOnes = true,
): string {
	return `${intervalStringSeconds(seconds, showOnes)}${type}`;
}

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
