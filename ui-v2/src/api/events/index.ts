import type { components } from "../prefect";

export type Event = components["schemas"]["ReceivedEvent"];
export type EventsFilter =
	components["schemas"]["Body_read_events_events_filter_post"];
export type EventsPage = components["schemas"]["EventPage"];
export type EventsCountFilter =
	components["schemas"]["Body_count_account_events_events_count_by__countable__post"];
export type EventsCount = components["schemas"]["EventCount"];

/**
 * Query key factory for events-related queries
 *
 * @property {function} all - Returns base key for all events queries
 * @property {function} lists - Returns key for all list-type events queries
 * @property {function} "lists-filter" - Returns key for all filtered list queries
 * @property {function} "list-filter" - Generates key for a specific filtered events query
 * @property {function} counts - Returns key for all count-type events queries
 * @property {function} count - Generates key for a specific count query with countable and filter
 * @property {function} history - Returns key for all history-type events queries
 * @property {function} historyFilter - Generates key for a specific history query with filter
 *
 * ```
 * all            => ['events']
 * lists          => ['events', 'list']
 * lists-filter   => ['events', 'list', 'filter']
 * list-filter    => ['events', 'list', 'filter', { ...filter }]
 * counts         => ['events', 'counts']
 * count          => ['events', 'counts', countable, { ...filter }]
 * history        => ['events', 'history']
 * historyFilter  => ['events', 'history', { ...filter }]
 * ```
 */
export const queryKeyFactory = {
	all: () => ["events"] as const,
	lists: () => [...queryKeyFactory.all(), "list"] as const,
	"lists-filter": () => [...queryKeyFactory.lists(), "filter"] as const,
	"list-filter": (filter: EventsFilter) =>
		[...queryKeyFactory["lists-filter"](), filter] as const,
	counts: () => [...queryKeyFactory.all(), "counts"] as const,
	count: (countable: string, filter: EventsCountFilter) =>
		[...queryKeyFactory.counts(), countable, filter] as const,
	history: () => [...queryKeyFactory.all(), "history"] as const,
	historyFilter: (filter: EventsFilter) =>
		[...queryKeyFactory.history(), filter] as const,
};
