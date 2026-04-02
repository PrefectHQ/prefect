import type { components } from "../prefect";
import type { EventsCountFilter, EventsFilter } from "./index";

/**
 * Default events to exclude from event queries.
 * These events are typically high-volume and not useful for most UI displays.
 */
export const DEFAULT_EXCLUDE_EVENTS = ["prefect.log.write"];

/**
 * Maximum number of buckets allowed by the backend for time-based event counts.
 * The backend will return a 422 error if this limit is exceeded.
 */
const MAX_BUCKETS = 1000;

/**
 * Search parameters for events filtering.
 * Supports both "span" mode (relative time from now) and "range" mode (explicit start/end).
 */
export type EventsSearchParams = {
	/** Mode for date range selection */
	rangeType?: "span" | "range";
	/** Seconds offset from now for span mode (negative = past, positive = future) */
	seconds?: number;
	/** Start datetime ISO string for range mode */
	start?: string;
	/** End datetime ISO string for range mode */
	end?: string;
	/** Resource ID prefixes to filter by */
	resource?: string[];
	/** Event type selections to filter by. Items ending with ".*" are treated as prefix filters; others as exact name matches. */
	event?: string[];
	/** Sort order for events */
	order?: "ASC" | "DESC";
};

/**
 * Rounds a date to the nearest minute to stabilize query keys.
 * This prevents cache busting from millisecond differences between renders.
 */
function roundToMinute(date: Date): Date {
	const rounded = new Date(date);
	rounded.setSeconds(0, 0);
	return rounded;
}

/**
 * Calculates the date range from search parameters.
 * Supports both "span" mode (relative time) and "range" mode (explicit dates).
 *
 * @param search - The search parameters containing date range configuration
 * @returns Object with `from` and `to` ISO datetime strings
 *
 * @example
 * ```ts
 * // Span mode: last 24 hours
 * getDateRangeFromSearch({ rangeType: "span", seconds: -86400 })
 * // => { from: "2024-01-14T10:00:00.000Z", to: "2024-01-15T10:00:00.000Z" }
 *
 * // Range mode: explicit dates
 * getDateRangeFromSearch({
 *   rangeType: "range",
 *   start: "2024-01-01T00:00:00.000Z",
 *   end: "2024-01-31T23:59:59.999Z"
 * })
 * ```
 */
export function getDateRangeFromSearch(search: EventsSearchParams): {
	from: string;
	to: string;
} {
	if (search.rangeType === "range" && search.start && search.end) {
		return { from: search.start, to: search.end };
	}

	// Default to span mode (relative time from now)
	const now = roundToMinute(new Date());
	const seconds = search.seconds ?? -86400; // Default to last 24 hours
	const then = new Date(now.getTime() + seconds * 1000);
	const [a, b] = [now, then].sort((x, y) => x.getTime() - y.getTime());
	return { from: a.toISOString(), to: b.toISOString() };
}

/**
 * Calculates the appropriate time unit for event counting based on the date range.
 * This ensures the number of buckets stays within the backend's limit of 1000.
 *
 * The logic selects the smallest time unit that won't exceed the bucket limit:
 * - minute: for ranges <= 1000 minutes (~16.7 hours)
 * - hour: for ranges <= 1000 hours (~41.7 days)
 * - day: for larger ranges
 *
 * @param startDate - Start of the date range (ISO string or Date)
 * @param endDate - End of the date range (ISO string or Date)
 * @returns The appropriate time unit: "minute", "hour", or "day"
 *
 * @example
 * ```ts
 * // Short range (1 hour) -> minute granularity
 * calculateTimeUnit("2024-01-15T09:00:00Z", "2024-01-15T10:00:00Z")
 * // => "minute"
 *
 * // Medium range (1 day) -> hour granularity
 * calculateTimeUnit("2024-01-15T00:00:00Z", "2024-01-16T00:00:00Z")
 * // => "hour"
 *
 * // Large range (1 month) -> day granularity
 * calculateTimeUnit("2024-01-01T00:00:00Z", "2024-01-31T23:59:59Z")
 * // => "day"
 * ```
 */
export function calculateTimeUnit(
	startDate: string | Date,
	endDate: string | Date,
): components["schemas"]["TimeUnit"] {
	const start = typeof startDate === "string" ? new Date(startDate) : startDate;
	const end = typeof endDate === "string" ? new Date(endDate) : endDate;

	const diffSeconds = Math.abs(end.getTime() - start.getTime()) / 1000;
	const diffMinutes = diffSeconds / 60;
	const diffHours = diffMinutes / 60;

	// Select the smallest unit that keeps buckets under the limit
	if (diffMinutes <= MAX_BUCKETS) {
		return "minute";
	}

	if (diffHours <= MAX_BUCKETS) {
		return "hour";
	}

	return "day";
}

/**
 * Separates event type selections into prefix filters and exact name filters.
 *
 * Items ending with ".*" are treated as wildcard prefix filters (the ".*" suffix
 * is stripped to produce the prefix). All other items are treated as exact name
 * matches. This mirrors V1 behavior where users could select both "prefect.flow-run.*"
 * (prefix) and "prefect.flow-run.Completed" (exact).
 */
export function separateEventSelections(events: string[]): {
	prefix: string[];
	name: string[];
} {
	const prefix: string[] = [];
	const name: string[] = [];

	for (const event of events) {
		if (event.endsWith(".*")) {
			prefix.push(event.slice(0, -1));
		} else {
			name.push(event);
		}
	}

	return { prefix, name };
}

/**
 * Builds an EventNameFilter from event selections and default exclusions.
 *
 * Separates selections into prefix and exact name arrays, applies default
 * exclusions via exclude_name, and removes any explicitly-selected exact names
 * from the exclusion list (opt-in mechanism).
 */
function buildEventNameFilter(
	events: string[] | undefined,
): components["schemas"]["EventNameFilter"] {
	const eventNameFilter: components["schemas"]["EventNameFilter"] = {};

	if (events && events.length > 0) {
		const { prefix, name } = separateEventSelections(events);

		if (prefix.length > 0) {
			eventNameFilter.prefix = prefix;
		}
		if (name.length > 0) {
			eventNameFilter.name = name;
		}

		// Exclude default events unless explicitly selected by exact name
		const excludeName = DEFAULT_EXCLUDE_EVENTS.filter(
			(excluded) => !name.includes(excluded),
		);
		if (excludeName.length > 0) {
			eventNameFilter.exclude_name = excludeName;
		}
	} else {
		// No selections: just apply default exclusions
		eventNameFilter.exclude_name = DEFAULT_EXCLUDE_EVENTS;
	}

	return eventNameFilter;
}

/**
 * Builds an EventsFilter from URL search parameters for the /events/filter endpoint.
 *
 * This function converts URL search parameters into the filter format expected by
 * the events API. It handles date range calculation, resource filtering, event
 * name filtering (both prefix and exact), and applies default exclusions.
 * Users can opt-in to excluded events by selecting them explicitly.
 *
 * @param search - The search parameters from the URL
 * @returns An EventsFilter object ready for the API
 *
 * @example
 * ```ts
 * const filter = buildEventsFilterFromSearch({
 *   rangeType: "span",
 *   seconds: -86400,
 *   resource: ["prefect.flow-run.abc123"],
 *   event: ["prefect.flow-run.*", "prefect.flow-run.Completed"],
 *   order: "DESC"
 * });
 *
 * // Use with the query factory
 * const { data } = useQuery(buildFilterEventsQuery(filter));
 * ```
 */
export function buildEventsFilterFromSearch(
	search: EventsSearchParams,
): EventsFilter {
	const { from, to } = getDateRangeFromSearch(search);

	const eventFilter: components["schemas"]["EventFilter"] = {
		occurred: {
			since: from,
			until: to,
		},
		order: search.order ?? "DESC",
	};

	// Add resource filter if specified
	if (search.resource && search.resource.length > 0) {
		eventFilter.any_resource = {
			id_prefix: search.resource,
		};
	}

	eventFilter.event = buildEventNameFilter(search.event);

	return {
		filter: eventFilter,
		limit: 50,
	};
}

/**
 * Builds an EventsCountFilter from URL search parameters for the /events/count-by/{countable} endpoint.
 *
 * This function converts URL search parameters into the filter format expected by
 * the events count API. It automatically calculates the appropriate time unit based
 * on the date range to prevent exceeding the backend's bucket limit.
 *
 * @param search - The search parameters from the URL
 * @returns An EventsCountFilter object ready for the API
 *
 * @example
 * ```ts
 * const filter = buildEventsCountFilterFromSearch({
 *   rangeType: "span",
 *   seconds: -86400,
 *   resource: ["prefect.flow-run.abc123"]
 * });
 *
 * // Use with the query factory for time-series data
 * const { data } = useQuery(buildEventsCountQuery("time", filter));
 *
 * // Or for event counts by day
 * const { data } = useQuery(buildEventsCountQuery("day", filter));
 * ```
 */
export function buildEventsCountFilterFromSearch(
	search: EventsSearchParams,
): EventsCountFilter {
	const { from, to } = getDateRangeFromSearch(search);
	const timeUnit = calculateTimeUnit(from, to);

	const eventFilter: components["schemas"]["EventFilter"] = {
		occurred: {
			since: from,
			until: to,
		},
		order: search.order ?? "DESC",
	};

	// Add resource filter if specified
	if (search.resource && search.resource.length > 0) {
		eventFilter.any_resource = {
			id_prefix: search.resource,
		};
	}

	eventFilter.event = buildEventNameFilter(search.event);

	return {
		filter: eventFilter,
		time_unit: timeUnit,
		time_interval: 1,
	};
}
