import {
	addSeconds,
	endOfToday,
	format,
	isAfter,
	isBefore,
	startOfToday,
} from "date-fns";
import type { DateRangeSelectSpanValue, DateRangeSelectValue } from "./types";

export function getDateRangeLabel(value: DateRangeSelectValue): string {
	if (!value) return "";

	switch (value.type) {
		case "span":
			return getSpanLabel(value.seconds);
		case "range":
			return `${format(value.startDate, "MMM d, yyyy")} - ${format(value.endDate, "MMM d, yyyy")}`;
		case "period":
			return value.period;
		case "around":
			return `${value.quantity} ${value.unit}${value.quantity > 1 ? "s" : ""} around ${format(value.date, "MMM d, yyyy")}`;
		default:
			return "";
	}
}

export function getSpanLabel(seconds: number): string {
	const absSeconds = Math.abs(seconds);

	if (absSeconds === 3600) return "1 hour";
	if (absSeconds === 86400) return "1 day";
	if (absSeconds === 604800) return "7 days";
	if (absSeconds === 2592000) return "30 days";
	if (absSeconds === 7776000) return "90 days";

	// Calculate based on seconds
	if (absSeconds < 60)
		return `${absSeconds} second${absSeconds !== 1 ? "s" : ""}`;
	if (absSeconds < 3600) {
		const minutes = Math.floor(absSeconds / 60);
		return `${minutes} minute${minutes !== 1 ? "s" : ""}`;
	}
	if (absSeconds < 86400) {
		const hours = Math.floor(absSeconds / 3600);
		return `${hours} hour${hours !== 1 ? "s" : ""}`;
	}

	const days = Math.floor(absSeconds / 86400);
	return `${days} day${days !== 1 ? "s" : ""}`;
}

export function mapDateRangeToDateRange(
	value: DateRangeSelectValue,
): { startDate: Date; endDate: Date; timeSpanInSeconds: number } | null {
	if (!value) return null;

	const now = new Date();

	switch (value.type) {
		case "span": {
			const startDate = addSeconds(now, value.seconds);
			return {
				startDate,
				endDate: now,
				timeSpanInSeconds: Math.abs(value.seconds),
			};
		}
		case "range": {
			const timeSpanInSeconds = Math.abs(
				(value.endDate.getTime() - value.startDate.getTime()) / 1000,
			);
			return {
				startDate: value.startDate,
				endDate: value.endDate,
				timeSpanInSeconds,
			};
		}
		case "period": {
			if (value.period === "Today") {
				const startDate = startOfToday();
				const endDate = endOfToday();
				return {
					startDate,
					endDate,
					timeSpanInSeconds: 86400,
				};
			}
			return null;
		}
		case "around": {
			let secondsAmount = value.quantity;
			switch (value.unit) {
				case "minute":
					secondsAmount *= 60;
					break;
				case "hour":
					secondsAmount *= 3600;
					break;
				case "day":
					secondsAmount *= 86400;
					break;
			}

			const startDate = addSeconds(value.date, -secondsAmount);
			const endDate = addSeconds(value.date, secondsAmount);
			return {
				startDate,
				endDate,
				timeSpanInSeconds: secondsAmount * 2,
			};
		}
		default:
			return null;
	}
}

export const PRESET_RANGES: Array<{
	label: string;
	value: DateRangeSelectSpanValue;
}> = [
	{ label: "Last hour", value: { type: "span", seconds: -3600 } },
	{ label: "Last day", value: { type: "span", seconds: -86400 } },
	{ label: "Last 7 days", value: { type: "span", seconds: -604800 } },
	{ label: "Last 30 days", value: { type: "span", seconds: -2592000 } },
	{ label: "Last 90 days", value: { type: "span", seconds: -7776000 } },
];

export function isValidDateRange(
	value: DateRangeSelectValue,
	min?: Date,
	max?: Date,
): { valid: boolean; reason?: string } {
	if (!value) return { valid: true };

	const range = mapDateRangeToDateRange(value);
	if (!range) return { valid: false, reason: "Invalid date range" };

	const { startDate, endDate } = range;

	if (min && isBefore(startDate, min)) {
		return {
			valid: false,
			reason: `Start date cannot be before ${format(min, "MMM d, yyyy")}`,
		};
	}

	if (max && isAfter(endDate, max)) {
		return {
			valid: false,
			reason: `End date cannot be after ${format(max, "MMM d, yyyy")}`,
		};
	}

	return { valid: true };
}
