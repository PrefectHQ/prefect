import { keepPreviousData, queryOptions } from "@tanstack/react-query";
import type { components } from "../prefect";
import { getQueryService } from "../service";

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
	historyFilter: (filter: EventsCountFilter) =>
		[...queryKeyFactory.history(), filter] as const,
	detail: (eventId: string, eventDate?: Date) =>
		[
			...queryKeyFactory.all(),
			"detail",
			eventId,
			eventDate?.toISOString(),
		] as const,
};

/**
 * Builds a query configuration for fetching filtered events
 *
 * @param filter - Filter parameters for the events query
 * @param refetchInterval - Interval for refetching events (default 60 seconds)
 * @returns Query configuration object for use with TanStack Query
 *
 * @example
 * ```ts
 * const { data } = useQuery(buildFilterEventsQuery({
 *   filter: {
 *     any_resource: { id: ["prefect.flow-run.123"] },
 *     order: "DESC"
 *   },
 *   limit: 100
 * }));
 * ```
 */
export const buildFilterEventsQuery = (
	filter: EventsFilter,
	refetchInterval = 60_000,
) =>
	queryOptions({
		queryKey: queryKeyFactory["list-filter"](filter),
		queryFn: async () => {
			const res = await (await getQueryService()).POST("/events/filter", {
				body: filter,
			});
			if (!res.data) {
				throw new Error("'data' expected");
			}
			return res.data;
		},
		placeholderData: keepPreviousData,
		staleTime: 1000,
		refetchInterval,
	});

/**
 * Builds a query configuration for fetching event counts by dimension
 *
 * @param countable - The dimension to count by: "day", "time", "event", or "resource"
 * @param filter - Filter parameters for the events count query
 * @param refetchInterval - Interval for refetching counts (default 60 seconds)
 * @returns Query configuration object for use with TanStack Query
 *
 * @example
 * ```ts
 * const { data } = useQuery(buildEventsCountQuery("day", {
 *   filter: {
 *     occurred: {
 *       since: "2024-01-01T00:00:00.000Z",
 *       until: "2024-01-31T23:59:59.999Z"
 *     }
 *   },
 *   time_unit: "day",
 *   time_interval: 1
 * }));
 * ```
 */
export const buildEventsCountQuery = (
	countable: "day" | "time" | "event" | "resource",
	filter: EventsCountFilter,
	refetchInterval = 60_000,
) =>
	queryOptions({
		queryKey: queryKeyFactory.count(countable, filter),
		queryFn: async () => {
			const res = await (await getQueryService()).POST(
				"/events/count-by/{countable}",
				{
					params: { path: { countable } },
					body: filter,
				},
			);
			return res.data ?? [];
		},
		refetchInterval,
	});

/**
 * Builds a query configuration for fetching event history (time-series data)
 *
 * @param filter - Filter parameters for the events history query
 * @param refetchInterval - Interval for refetching history (default 60 seconds)
 * @returns Query configuration object for use with TanStack Query
 *
 * @example
 * ```ts
 * const { data } = useQuery(buildEventsHistoryQuery({
 *   filter: {
 *     occurred: {
 *       since: "2024-01-01T00:00:00.000Z",
 *       until: "2024-01-31T23:59:59.999Z"
 *     }
 *   },
 *   time_unit: "hour",
 *   time_interval: 1
 * }));
 * ```
 */
export const buildEventsHistoryQuery = (
	filter: EventsCountFilter,
	refetchInterval = 60_000,
) =>
	queryOptions({
		queryKey: queryKeyFactory.historyFilter(filter),
		queryFn: async () => {
			const res = await (await getQueryService()).POST(
				"/events/count-by/{countable}",
				{
					params: { path: { countable: "time" } },
					body: filter,
				},
			);
			return res.data ?? [];
		},
		placeholderData: keepPreviousData,
		staleTime: 1000,
		refetchInterval,
	});

/**
 * Builds a query configuration for fetching the next page of events
 *
 * @param nextPageUrl - The full next_page URL from the previous response
 * @returns Query configuration object for use with TanStack Query
 *
 * @example
 * ```ts
 * const { data: firstPage } = useQuery(buildFilterEventsQuery(filter));
 * // If there's a next page, fetch it
 * if (firstPage.next_page) {
 *   const { data: nextPage } = useQuery(buildEventsNextPageQuery(firstPage.next_page));
 * }
 * ```
 */
export const buildEventsNextPageQuery = (nextPageUrl: string) =>
	queryOptions({
		queryKey: [...queryKeyFactory.lists(), "next", nextPageUrl] as const,
		queryFn: async () => {
			const url = new URL(nextPageUrl);
			const pageToken = url.searchParams.get("page-token");
			if (!pageToken) {
				throw new Error(
					"'page-token' query parameter expected in next_page URL",
				);
			}
			const res = await (await getQueryService()).GET("/events/filter/next", {
				params: { query: { "page-token": pageToken } },
			});
			if (!res.data) {
				throw new Error("'data' expected");
			}
			return res.data;
		},
		staleTime: Number.POSITIVE_INFINITY,
	});

export const buildGetEventQuery = (eventId: string, eventDate: Date) => {
	return queryOptions({
		queryKey: queryKeyFactory.detail(eventId, eventDate),
		queryFn: async () => {
			const startDate = new Date(eventDate);
			startDate.setHours(0, 0, 0, 0);
			const endDate = new Date(startDate);
			endDate.setDate(endDate.getDate() + 1);

			const filter: EventsFilter = {
				filter: {
					id: { id: [eventId] },
					occurred: {
						since: startDate.toISOString(),
						until: endDate.toISOString(),
					},
					order: "DESC",
				},
				limit: 1,
			};

			const res = await (await getQueryService()).POST("/events/filter", {
				body: filter,
			});
			if (!res.data?.events?.[0]) {
				throw new Error("Event not found");
			}
			return res.data.events[0];
		},
		staleTime: 60_000,
	});
};

export * from "./filters";
