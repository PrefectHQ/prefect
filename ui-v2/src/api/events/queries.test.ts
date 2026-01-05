import { QueryClient, useSuspenseQuery } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";
import type { EventsCountFilter, EventsFilter, EventsPage } from ".";
import {
	buildEventsCountQuery,
	buildEventsHistoryQuery,
	buildEventsNextPageQuery,
	buildFilterEventsQuery,
} from ".";

describe("events query factories", () => {
	describe("buildFilterEventsQuery", () => {
		const mockFilterEventsAPI = (response: EventsPage) => {
			server.use(
				http.post(buildApiUrl("/events/filter"), () => {
					return HttpResponse.json(response);
				}),
			);
		};

		it("fetches filtered events with default parameters", async () => {
			const mockResponse: EventsPage = {
				events: [
					{
						id: "event-1",
						occurred: "2024-01-15T10:00:00.000Z",
						event: "prefect.flow-run.completed",
						resource: { "prefect.resource.id": "prefect.flow-run.123" },
						payload: {},
						received: "2024-01-15T10:00:01.000Z",
					},
				],
				total: 1,
				next_page: null,
			};
			mockFilterEventsAPI(mockResponse);

			const filter: EventsFilter = {
				filter: {
					any_resource: { id: ["prefect.flow-run.123"] },
					order: "DESC",
				},
				limit: 100,
			};

			const queryClient = new QueryClient();
			const { result } = renderHook(
				() => useSuspenseQuery(buildFilterEventsQuery(filter)),
				{ wrapper: createWrapper({ queryClient }) },
			);

			await waitFor(() => {
				expect(result.current.data).toEqual(mockResponse);
			});
		});

		it("uses the provided refetch interval", () => {
			const filter: EventsFilter = {
				filter: { order: "DESC" },
				limit: 50,
			};
			const customRefetchInterval = 120_000;

			const { refetchInterval } = buildFilterEventsQuery(
				filter,
				customRefetchInterval,
			);

			expect(refetchInterval).toBe(customRefetchInterval);
		});

		it("uses default refetch interval of 60 seconds", () => {
			const filter: EventsFilter = {
				filter: { order: "DESC" },
				limit: 50,
			};

			const { refetchInterval } = buildFilterEventsQuery(filter);

			expect(refetchInterval).toBe(60_000);
		});

		it("has correct query key structure", () => {
			const filter: EventsFilter = {
				filter: { order: "DESC" },
				limit: 50,
			};

			const { queryKey } = buildFilterEventsQuery(filter);

			expect(queryKey).toEqual(["events", "list", "filter", filter]);
		});

		it("includes placeholderData and staleTime options", () => {
			const filter: EventsFilter = {
				filter: { order: "DESC" },
				limit: 50,
			};

			const queryOptions = buildFilterEventsQuery(filter);

			expect(queryOptions.placeholderData).toBeDefined();
			expect(queryOptions.staleTime).toBe(1000);
		});
	});

	describe("buildEventsCountQuery", () => {
		const mockEventsCountAPI = (
			countable: string,
			response: Array<{ value: string; label: string; count: number }>,
		) => {
			server.use(
				http.post(buildApiUrl(`/events/count-by/${countable}`), () => {
					return HttpResponse.json(response);
				}),
			);
		};

		it("fetches event counts by day", async () => {
			const mockResponse = [
				{ value: "2024-01-15", label: "2024-01-15", count: 10 },
				{ value: "2024-01-16", label: "2024-01-16", count: 5 },
			];
			mockEventsCountAPI("day", mockResponse);

			const filter: EventsCountFilter = {
				filter: {
					occurred: {
						since: "2024-01-01T00:00:00.000Z",
						until: "2024-01-31T23:59:59.999Z",
					},
					order: "DESC",
				},
				time_unit: "day",
				time_interval: 1,
			};

			const queryClient = new QueryClient();
			const { result } = renderHook(
				() => useSuspenseQuery(buildEventsCountQuery("day", filter)),
				{ wrapper: createWrapper({ queryClient }) },
			);

			await waitFor(() => {
				expect(result.current.data).toEqual(mockResponse);
			});
		});

		it("fetches event counts by resource", async () => {
			const mockResponse = [
				{
					value: "prefect.flow-run.123",
					label: "prefect.flow-run.123",
					count: 25,
				},
			];
			mockEventsCountAPI("resource", mockResponse);

			const filter: EventsCountFilter = {
				filter: { order: "DESC" },
				time_unit: "day",
				time_interval: 1,
			};

			const queryClient = new QueryClient();
			const { result } = renderHook(
				() => useSuspenseQuery(buildEventsCountQuery("resource", filter)),
				{ wrapper: createWrapper({ queryClient }) },
			);

			await waitFor(() => {
				expect(result.current.data).toEqual(mockResponse);
			});
		});

		it("uses the provided refetch interval", () => {
			const filter: EventsCountFilter = {
				filter: { order: "DESC" },
				time_unit: "day",
				time_interval: 1,
			};
			const customRefetchInterval = 120_000;

			const { refetchInterval } = buildEventsCountQuery(
				"day",
				filter,
				customRefetchInterval,
			);

			expect(refetchInterval).toBe(customRefetchInterval);
		});

		it("returns empty array when data is missing", async () => {
			server.use(
				http.post(buildApiUrl("/events/count-by/day"), () => {
					return HttpResponse.json(null);
				}),
			);

			const filter: EventsCountFilter = {
				filter: { order: "DESC" },
				time_unit: "day",
				time_interval: 1,
			};

			const queryClient = new QueryClient();
			const { result } = renderHook(
				() => useSuspenseQuery(buildEventsCountQuery("day", filter)),
				{ wrapper: createWrapper({ queryClient }) },
			);

			await waitFor(() => {
				expect(result.current.data).toEqual([]);
			});
		});
	});

	describe("buildEventsHistoryQuery", () => {
		const mockEventsHistoryAPI = (
			response: Array<{ value: string; label: string; count: number }>,
		) => {
			server.use(
				http.post(buildApiUrl("/events/count-by/time"), () => {
					return HttpResponse.json(response);
				}),
			);
		};

		it("fetches event history (time-series data)", async () => {
			const mockResponse = [
				{ value: "2024-01-15T10:00:00.000Z", label: "10:00", count: 5 },
				{ value: "2024-01-15T11:00:00.000Z", label: "11:00", count: 8 },
			];
			mockEventsHistoryAPI(mockResponse);

			const filter: EventsCountFilter = {
				filter: {
					occurred: {
						since: "2024-01-15T00:00:00.000Z",
						until: "2024-01-15T23:59:59.999Z",
					},
					order: "ASC",
				},
				time_unit: "hour",
				time_interval: 1,
			};

			const queryClient = new QueryClient();
			const { result } = renderHook(
				() => useSuspenseQuery(buildEventsHistoryQuery(filter)),
				{ wrapper: createWrapper({ queryClient }) },
			);

			await waitFor(() => {
				expect(result.current.data).toEqual(mockResponse);
			});
		});

		it("uses the provided refetch interval", () => {
			const filter: EventsCountFilter = {
				filter: { order: "DESC" },
				time_unit: "hour",
				time_interval: 1,
			};
			const customRefetchInterval = 120_000;

			const { refetchInterval } = buildEventsHistoryQuery(
				filter,
				customRefetchInterval,
			);

			expect(refetchInterval).toBe(customRefetchInterval);
		});

		it("uses default refetch interval of 60 seconds", () => {
			const filter: EventsCountFilter = {
				filter: { order: "DESC" },
				time_unit: "hour",
				time_interval: 1,
			};

			const { refetchInterval } = buildEventsHistoryQuery(filter);

			expect(refetchInterval).toBe(60_000);
		});

		it("returns empty array when data is missing", async () => {
			server.use(
				http.post(buildApiUrl("/events/count-by/time"), () => {
					return HttpResponse.json(null);
				}),
			);

			const filter: EventsCountFilter = {
				filter: { order: "DESC" },
				time_unit: "hour",
				time_interval: 1,
			};

			const queryClient = new QueryClient();
			const { result } = renderHook(
				() => useSuspenseQuery(buildEventsHistoryQuery(filter)),
				{ wrapper: createWrapper({ queryClient }) },
			);

			await waitFor(() => {
				expect(result.current.data).toEqual([]);
			});
		});
	});

	describe("buildEventsNextPageQuery", () => {
		const mockNextPageAPI = (response: EventsPage) => {
			server.use(
				http.get(buildApiUrl("/events/filter/next"), () => {
					return HttpResponse.json(response);
				}),
			);
		};

		it("fetches next page of events using page token", async () => {
			const mockResponse: EventsPage = {
				events: [
					{
						id: "event-2",
						occurred: "2024-01-15T11:00:00.000Z",
						event: "prefect.flow-run.completed",
						resource: { "prefect.resource.id": "prefect.flow-run.456" },
						payload: {},
						received: "2024-01-15T11:00:01.000Z",
					},
				],
				total: 100,
				next_page: "http://test/api/events/filter/next?page-token=token2",
			};
			mockNextPageAPI(mockResponse);

			const nextPageUrl =
				"http://test/api/events/filter/next?page-token=token1";

			const queryClient = new QueryClient();
			const { result } = renderHook(
				() => useSuspenseQuery(buildEventsNextPageQuery(nextPageUrl)),
				{ wrapper: createWrapper({ queryClient }) },
			);

			await waitFor(() => {
				expect(result.current.data).toEqual(mockResponse);
			});
		});

		it("has correct query key structure", () => {
			const nextPageUrl =
				"http://test/api/events/filter/next?page-token=token1";

			const { queryKey } = buildEventsNextPageQuery(nextPageUrl);

			expect(queryKey).toEqual(["events", "list", "next", nextPageUrl]);
		});

		it("has staleTime set to Infinity", () => {
			const nextPageUrl =
				"http://test/api/events/filter/next?page-token=token1";

			const { staleTime } = buildEventsNextPageQuery(nextPageUrl);

			expect(staleTime).toBe(Number.POSITIVE_INFINITY);
		});

		it("extracts page-token from URL correctly", () => {
			const nextPageUrl =
				"http://test/api/events/filter/next?page-token=abc123xyz";

			const queryOptions = buildEventsNextPageQuery(nextPageUrl);

			expect(queryOptions.queryFn).toBeDefined();
		});

		it("handles URLs with additional query parameters", () => {
			const nextPageUrl =
				"http://test/api/events/filter/next?page-token=token1&other=param";

			const { queryKey } = buildEventsNextPageQuery(nextPageUrl);

			expect(queryKey).toEqual(["events", "list", "next", nextPageUrl]);
		});
	});
});
