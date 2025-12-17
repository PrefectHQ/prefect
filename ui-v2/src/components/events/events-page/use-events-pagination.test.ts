import { QueryClient } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import type { EventsFilter } from "@/api/events";
import { useEventsPagination } from "./use-events-pagination";

describe("useEventsPagination", () => {
	const createTestQueryClient = () => {
		return new QueryClient({
			defaultOptions: {
				queries: {
					retry: false,
				},
			},
		});
	};

	const createMockEvent = (id: string) => ({
		id,
		occurred: new Date().toISOString(),
		event: `test.event.${id}`,
		resource: { "prefect.resource.id": `resource-${id}` },
		related: [],
		payload: {},
		received: new Date().toISOString(),
	});

	const defaultFilter: EventsFilter = {
		filter: {
			occurred: {
				since: "2024-01-01T00:00:00.000Z",
				until: "2024-12-31T23:59:59.999Z",
			},
			order: "DESC",
		},
		limit: 50,
	};

	beforeEach(() => {
		server.resetHandlers();
	});

	describe("first page loading", () => {
		it("loads the first page of events", async () => {
			const mockEvents = [createMockEvent("1"), createMockEvent("2")];
			const queryClient = createTestQueryClient();

			server.use(
				http.post(buildApiUrl("/events/filter"), () => {
					return HttpResponse.json({
						events: mockEvents,
						total: 2,
						next_page: null,
					});
				}),
			);

			const { result } = renderHook(
				() => useEventsPagination({ filter: defaultFilter }),
				{ wrapper: createWrapper({ queryClient }) },
			);

			await waitFor(() => {
				expect(result.current.events).toHaveLength(2);
			});

			expect(result.current.currentPage).toBe(1);
			expect(result.current.total).toBe(2);
			expect(result.current.totalPages).toBe(1);
			expect(result.current.isLoadingNextPage).toBe(false);
		});

		it("calculates total pages correctly based on PAGE_SIZE of 50", async () => {
			const queryClient = createTestQueryClient();

			server.use(
				http.post(buildApiUrl("/events/filter"), () => {
					return HttpResponse.json({
						events: [createMockEvent("1")],
						total: 125,
						next_page: "http://test/api/events/filter/next?page-token=token1",
					});
				}),
			);

			const { result } = renderHook(
				() => useEventsPagination({ filter: defaultFilter }),
				{ wrapper: createWrapper({ queryClient }) },
			);

			await waitFor(() => {
				expect(result.current.totalPages).toBe(3);
			});
		});
	});

	describe("navigation to subsequent pages", () => {
		it("navigates to page 2 when goToNextPage is called", async () => {
			const queryClient = createTestQueryClient();
			const page1Events = [createMockEvent("1")];
			const page2Events = [createMockEvent("2")];

			server.use(
				http.post(buildApiUrl("/events/filter"), () => {
					return HttpResponse.json({
						events: page1Events,
						total: 100,
						next_page: "http://test/api/events/filter/next?page-token=token1",
					});
				}),
				http.get(buildApiUrl("/events/filter/next"), () => {
					return HttpResponse.json({
						events: page2Events,
						total: 100,
						next_page: "http://test/api/events/filter/next?page-token=token2",
					});
				}),
			);

			const { result } = renderHook(
				() => useEventsPagination({ filter: defaultFilter }),
				{ wrapper: createWrapper({ queryClient }) },
			);

			await waitFor(() => {
				expect(result.current.events).toHaveLength(1);
			});

			act(() => {
				result.current.goToNextPage();
			});

			await waitFor(() => {
				expect(result.current.currentPage).toBe(2);
				expect(result.current.events[0].id).toBe("2");
			});
		});

		it("navigates back to page 1 when goToPreviousPage is called", async () => {
			const queryClient = createTestQueryClient();
			const page1Events = [createMockEvent("1")];
			const page2Events = [createMockEvent("2")];

			server.use(
				http.post(buildApiUrl("/events/filter"), () => {
					return HttpResponse.json({
						events: page1Events,
						total: 100,
						next_page: "http://test/api/events/filter/next?page-token=token1",
					});
				}),
				http.get(buildApiUrl("/events/filter/next"), () => {
					return HttpResponse.json({
						events: page2Events,
						total: 100,
						next_page: null,
					});
				}),
			);

			const { result } = renderHook(
				() => useEventsPagination({ filter: defaultFilter }),
				{ wrapper: createWrapper({ queryClient }) },
			);

			await waitFor(() => {
				expect(result.current.events).toHaveLength(1);
			});

			act(() => {
				result.current.goToNextPage();
			});

			await waitFor(() => {
				expect(result.current.currentPage).toBe(2);
			});

			act(() => {
				result.current.goToPreviousPage();
			});

			expect(result.current.currentPage).toBe(1);
			expect(result.current.events[0].id).toBe("1");
		});

		it("navigates to a specific page using goToPage", async () => {
			const queryClient = createTestQueryClient();

			server.use(
				http.post(buildApiUrl("/events/filter"), () => {
					return HttpResponse.json({
						events: [createMockEvent("1")],
						total: 100,
						next_page: "http://test/api/events/filter/next?page-token=token1",
					});
				}),
				http.get(buildApiUrl("/events/filter/next"), () => {
					return HttpResponse.json({
						events: [createMockEvent("2")],
						total: 100,
						next_page: null,
					});
				}),
			);

			const { result } = renderHook(
				() => useEventsPagination({ filter: defaultFilter }),
				{ wrapper: createWrapper({ queryClient }) },
			);

			await waitFor(() => {
				expect(result.current.events).toHaveLength(1);
			});

			act(() => {
				result.current.goToPage(2);
			});

			await waitFor(() => {
				expect(result.current.currentPage).toBe(2);
			});
		});
	});

	describe("token vault caching behavior", () => {
		it("stores next_page tokens from API responses", async () => {
			const queryClient = createTestQueryClient();
			let page2RequestCount = 0;

			server.use(
				http.post(buildApiUrl("/events/filter"), () => {
					return HttpResponse.json({
						events: [createMockEvent("1")],
						total: 150,
						next_page: "http://test/api/events/filter/next?page-token=token1",
					});
				}),
				http.get(buildApiUrl("/events/filter/next"), () => {
					page2RequestCount++;
					return HttpResponse.json({
						events: [createMockEvent("2")],
						total: 150,
						next_page: "http://test/api/events/filter/next?page-token=token2",
					});
				}),
			);

			const { result } = renderHook(
				() => useEventsPagination({ filter: defaultFilter }),
				{ wrapper: createWrapper({ queryClient }) },
			);

			await waitFor(() => {
				expect(result.current.events).toHaveLength(1);
			});

			act(() => {
				result.current.goToNextPage();
			});

			await waitFor(() => {
				expect(result.current.currentPage).toBe(2);
				expect(result.current.events[0].id).toBe("2");
			});

			await waitFor(() => {
				expect(page2RequestCount).toBe(1);
			});

			act(() => {
				result.current.goToNextPage();
			});

			await waitFor(() => {
				expect(result.current.currentPage).toBe(3);
			});
		});

		it("allows navigation back to previously visited pages", async () => {
			const queryClient = createTestQueryClient();
			let page2RequestCount = 0;

			server.use(
				http.post(buildApiUrl("/events/filter"), () => {
					return HttpResponse.json({
						events: [createMockEvent("1")],
						total: 100,
						next_page: "http://test/api/events/filter/next?page-token=token1",
					});
				}),
				http.get(buildApiUrl("/events/filter/next"), () => {
					page2RequestCount++;
					return HttpResponse.json({
						events: [createMockEvent("2")],
						total: 100,
						next_page: null,
					});
				}),
			);

			const { result } = renderHook(
				() => useEventsPagination({ filter: defaultFilter }),
				{ wrapper: createWrapper({ queryClient }) },
			);

			await waitFor(() => {
				expect(result.current.events).toHaveLength(1);
			});

			act(() => {
				result.current.goToNextPage();
			});

			await waitFor(() => {
				expect(result.current.currentPage).toBe(2);
			});

			act(() => {
				result.current.goToPreviousPage();
			});

			expect(result.current.currentPage).toBe(1);

			act(() => {
				result.current.goToNextPage();
			});

			await waitFor(() => {
				expect(result.current.currentPage).toBe(2);
			});

			expect(page2RequestCount).toBe(1);
		});
	});

	describe("filter change resets", () => {
		it("resets to page 1 when filter changes", async () => {
			const queryClient = createTestQueryClient();

			server.use(
				http.post(buildApiUrl("/events/filter"), () => {
					return HttpResponse.json({
						events: [createMockEvent("1")],
						total: 100,
						next_page: "http://test/api/events/filter/next?page-token=token1",
					});
				}),
				http.get(buildApiUrl("/events/filter/next"), () => {
					return HttpResponse.json({
						events: [createMockEvent("2")],
						total: 100,
						next_page: null,
					});
				}),
			);

			const { result, rerender } = renderHook(
				({ filter }) => useEventsPagination({ filter }),
				{
					wrapper: createWrapper({ queryClient }),
					initialProps: { filter: defaultFilter },
				},
			);

			await waitFor(() => {
				expect(result.current.events).toHaveLength(1);
			});

			act(() => {
				result.current.goToNextPage();
			});

			await waitFor(() => {
				expect(result.current.currentPage).toBe(2);
			});

			const newFilter: EventsFilter = {
				filter: {
					occurred: {
						since: "2024-06-01T00:00:00.000Z",
						until: "2024-12-31T23:59:59.999Z",
					},
					order: "DESC",
				},
				limit: 50,
			};

			rerender({ filter: newFilter });

			await waitFor(() => {
				expect(result.current.currentPage).toBe(1);
			});
		});

		it("clears token vault when filter changes", async () => {
			const queryClient = createTestQueryClient();
			let filterCallCount = 0;

			server.use(
				http.post(buildApiUrl("/events/filter"), () => {
					filterCallCount++;
					return HttpResponse.json({
						events: [createMockEvent(`filter-${filterCallCount}`)],
						total: 100,
						next_page: `http://test/api/events/filter/next?page-token=token-${filterCallCount}`,
					});
				}),
				http.get(buildApiUrl("/events/filter/next"), () => {
					return HttpResponse.json({
						events: [createMockEvent("page2")],
						total: 100,
						next_page: null,
					});
				}),
			);

			const { result, rerender } = renderHook(
				({ filter }) => useEventsPagination({ filter }),
				{
					wrapper: createWrapper({ queryClient }),
					initialProps: { filter: defaultFilter },
				},
			);

			await waitFor(() => {
				expect(result.current.events).toHaveLength(1);
			});

			act(() => {
				result.current.goToNextPage();
			});

			await waitFor(() => {
				expect(result.current.currentPage).toBe(2);
			});

			const newFilter: EventsFilter = {
				filter: {
					occurred: {
						since: "2024-06-01T00:00:00.000Z",
						until: "2024-12-31T23:59:59.999Z",
					},
					order: "DESC",
				},
				limit: 50,
			};

			rerender({ filter: newFilter });

			await waitFor(() => {
				expect(result.current.currentPage).toBe(1);
			});

			// Wait for the new filter's first page data to be loaded and token to be stored
			await waitFor(() => {
				expect(result.current.events[0].id).toBe("filter-2");
			});

			act(() => {
				result.current.goToPage(2);
			});

			await waitFor(() => {
				expect(result.current.currentPage).toBe(2);
			});
		});
	});

	describe("loading states", () => {
		it("shows loading state when fetching next page", async () => {
			const queryClient = createTestQueryClient();
			let resolveNextPage: (() => void) | undefined;
			const nextPagePromise = new Promise<void>((resolve) => {
				resolveNextPage = resolve;
			});

			server.use(
				http.post(buildApiUrl("/events/filter"), () => {
					return HttpResponse.json({
						events: [createMockEvent("1")],
						total: 100,
						next_page: "http://test/api/events/filter/next?page-token=token1",
					});
				}),
				http.get(buildApiUrl("/events/filter/next"), async () => {
					await nextPagePromise;
					return HttpResponse.json({
						events: [createMockEvent("2")],
						total: 100,
						next_page: null,
					});
				}),
			);

			const { result } = renderHook(
				() => useEventsPagination({ filter: defaultFilter }),
				{ wrapper: createWrapper({ queryClient }) },
			);

			await waitFor(() => {
				expect(result.current.events).toHaveLength(1);
			});

			act(() => {
				result.current.goToNextPage();
			});

			await waitFor(() => {
				expect(result.current.isLoadingNextPage).toBe(true);
			});

			resolveNextPage?.();

			await waitFor(() => {
				expect(result.current.isLoadingNextPage).toBe(false);
			});
		});

		it("does not show loading state on first page", async () => {
			const queryClient = createTestQueryClient();

			server.use(
				http.post(buildApiUrl("/events/filter"), () => {
					return HttpResponse.json({
						events: [createMockEvent("1")],
						total: 50,
						next_page: null,
					});
				}),
			);

			const { result } = renderHook(
				() => useEventsPagination({ filter: defaultFilter }),
				{ wrapper: createWrapper({ queryClient }) },
			);

			await waitFor(() => {
				expect(result.current.events).toHaveLength(1);
			});

			expect(result.current.isLoadingNextPage).toBe(false);
		});
	});

	describe("edge cases", () => {
		it("does not navigate past the last page", async () => {
			const queryClient = createTestQueryClient();

			server.use(
				http.post(buildApiUrl("/events/filter"), () => {
					return HttpResponse.json({
						events: [createMockEvent("1")],
						total: 50,
						next_page: null,
					});
				}),
			);

			const { result } = renderHook(
				() => useEventsPagination({ filter: defaultFilter }),
				{ wrapper: createWrapper({ queryClient }) },
			);

			await waitFor(() => {
				expect(result.current.events).toHaveLength(1);
			});

			act(() => {
				result.current.goToNextPage();
			});

			expect(result.current.currentPage).toBe(1);
		});

		it("does not navigate before page 1", async () => {
			const queryClient = createTestQueryClient();

			server.use(
				http.post(buildApiUrl("/events/filter"), () => {
					return HttpResponse.json({
						events: [createMockEvent("1")],
						total: 50,
						next_page: null,
					});
				}),
			);

			const { result } = renderHook(
				() => useEventsPagination({ filter: defaultFilter }),
				{ wrapper: createWrapper({ queryClient }) },
			);

			await waitFor(() => {
				expect(result.current.events).toHaveLength(1);
			});

			act(() => {
				result.current.goToPreviousPage();
			});

			expect(result.current.currentPage).toBe(1);
		});

		it("does not navigate to invalid page numbers", async () => {
			const queryClient = createTestQueryClient();

			server.use(
				http.post(buildApiUrl("/events/filter"), () => {
					return HttpResponse.json({
						events: [createMockEvent("1")],
						total: 100,
						next_page: "http://test/api/events/filter/next?page-token=token1",
					});
				}),
			);

			const { result } = renderHook(
				() => useEventsPagination({ filter: defaultFilter }),
				{ wrapper: createWrapper({ queryClient }) },
			);

			await waitFor(() => {
				expect(result.current.events).toHaveLength(1);
			});

			act(() => {
				result.current.goToPage(0);
			});

			expect(result.current.currentPage).toBe(1);

			act(() => {
				result.current.goToPage(-1);
			});

			expect(result.current.currentPage).toBe(1);

			act(() => {
				result.current.goToPage(100);
			});

			expect(result.current.currentPage).toBe(1);
		});

		it("does not navigate to page without cached token", async () => {
			const queryClient = createTestQueryClient();

			server.use(
				http.post(buildApiUrl("/events/filter"), () => {
					return HttpResponse.json({
						events: [createMockEvent("1")],
						total: 150,
						next_page: "http://test/api/events/filter/next?page-token=token1",
					});
				}),
			);

			const { result } = renderHook(
				() => useEventsPagination({ filter: defaultFilter }),
				{ wrapper: createWrapper({ queryClient }) },
			);

			await waitFor(() => {
				expect(result.current.events).toHaveLength(1);
			});

			act(() => {
				result.current.goToPage(3);
			});

			expect(result.current.currentPage).toBe(1);
		});

		it("handles empty events list", async () => {
			const queryClient = createTestQueryClient();

			server.use(
				http.post(buildApiUrl("/events/filter"), () => {
					return HttpResponse.json({
						events: [],
						total: 0,
						next_page: null,
					});
				}),
			);

			const { result } = renderHook(
				() => useEventsPagination({ filter: defaultFilter }),
				{ wrapper: createWrapper({ queryClient }) },
			);

			await waitFor(() => {
				expect(result.current.events).toHaveLength(0);
			});

			expect(result.current.currentPage).toBe(1);
			expect(result.current.totalPages).toBe(0);
			expect(result.current.total).toBe(0);
		});
	});
});
