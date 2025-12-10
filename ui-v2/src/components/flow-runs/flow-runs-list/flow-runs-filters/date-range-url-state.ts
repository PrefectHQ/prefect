import type { DateRangeSelectValue } from "@/components/ui/date-range-select";
import { getMultiplierForUnit } from "@/components/ui/date-range-select";

// Constants for preset span values (in seconds)
const SECONDS_IN_HOUR = 3600;
const SECONDS_IN_DAY = 86400;
const PAST_24_HOURS_SECONDS = SECONDS_IN_DAY;
const PAST_7_DAYS_SECONDS = SECONDS_IN_DAY * 7;
const PAST_30_DAYS_SECONDS = SECONDS_IN_DAY * 30;

// URL-friendly preset names
export const DATE_RANGE_PRESETS = [
	"past-hour",
	"past-24-hours",
	"past-7-days",
	"past-30-days",
	"today",
] as const;

export type DateRangePreset = (typeof DATE_RANGE_PRESETS)[number];

export type DateRangeUrlState = {
	range?: DateRangePreset | undefined;
	start?: string | undefined;
	end?: string | undefined;
};

/**
 * Converts URL state to DateRangeSelectValue for the RichDateRangeSelector
 */
export function urlStateToDateRangeValue(
	state: DateRangeUrlState,
): DateRangeSelectValue {
	// If we have custom start/end dates, use range type
	if (state.start && state.end) {
		return {
			type: "range",
			startDate: new Date(state.start),
			endDate: new Date(state.end),
		};
	}

	// Handle preset ranges
	switch (state.range) {
		case "past-hour":
			return { type: "span", seconds: -SECONDS_IN_HOUR };
		case "past-24-hours":
			return { type: "span", seconds: -PAST_24_HOURS_SECONDS };
		case "past-7-days":
			return { type: "span", seconds: -PAST_7_DAYS_SECONDS };
		case "past-30-days":
			return { type: "span", seconds: -PAST_30_DAYS_SECONDS };
		case "today":
			return { type: "period", period: "Today" };
		default:
			return null;
	}
}

/**
 * Converts DateRangeSelectValue to URL state for persistence
 */
export function dateRangeValueToUrlState(
	value: DateRangeSelectValue,
): DateRangeUrlState {
	if (!value) {
		return {};
	}

	switch (value.type) {
		case "span": {
			const absSeconds = Math.abs(value.seconds);
			// Map common span values to presets
			if (absSeconds === SECONDS_IN_HOUR) {
				return { range: "past-hour" };
			}
			if (absSeconds === PAST_24_HOURS_SECONDS) {
				return { range: "past-24-hours" };
			}
			if (absSeconds === PAST_7_DAYS_SECONDS) {
				return { range: "past-7-days" };
			}
			if (absSeconds === PAST_30_DAYS_SECONDS) {
				return { range: "past-30-days" };
			}
			// For non-standard spans, convert to a concrete date range
			const now = new Date();
			const startDate = new Date(now.getTime() + value.seconds * 1000);
			const endDate = now;
			const [start, end] =
				value.seconds < 0 ? [startDate, endDate] : [endDate, startDate];
			return {
				start: start.toISOString(),
				end: end.toISOString(),
			};
		}
		case "period":
			if (value.period === "Today") {
				return { range: "today" };
			}
			return {};
		case "range":
			return {
				start: value.startDate.toISOString(),
				end: value.endDate.toISOString(),
			};
		case "around": {
			// Convert "around" to a concrete date range
			const multiplier = getMultiplierForUnit(value.unit);
			const seconds = Math.abs(value.quantity * multiplier);
			const startDate = new Date(value.date.getTime() - seconds * 1000);
			const endDate = new Date(value.date.getTime() + seconds * 1000);
			return {
				start: startDate.toISOString(),
				end: endDate.toISOString(),
			};
		}
		default:
			return {};
	}
}
