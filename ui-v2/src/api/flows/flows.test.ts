import { QueryClient, useQuery, useSuspenseQuery } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";
import type { components } from "@/api/prefect";
import { createFakeFlow } from "@/mocks";
import {
	buildCountFlowsFilteredQuery,
	buildFLowDetailsQuery,
	buildListFlowsQuery,
	queryKeyFactory,
	useDeleteFlowById,
} from ".";

type Flow = components["schemas"]["Flow"];

describe("flows api", () => {
	const mockFetchFlowsAPI = (flows: Array<Flow>) => {
		server.use(
			http.post(buildApiUrl("/flows/filter"), () => {
				return HttpResponse.json(flows);
			}),
		);
	};

	const mockFetchFlowAPI = (flow: Flow) => {
		server.use(
			http.get(buildApiUrl("/flows/:id"), () => {
				return HttpResponse.json(flow);
			}),
		);
	};

	const mockFetchCountFlowsAPI = (count: number) => {
		server.use(
			http.post(buildApiUrl("/flows/count"), () => {
				return HttpResponse.json(count);
			}),
		);
	};

	describe("flowsQueryParams", () => {
		it("fetches paginated flows with default parameters", async () => {
			const flow = createFakeFlow();
			mockFetchFlowsAPI([flow]);

			const queryClient = new QueryClient();
			const { result } = renderHook(
				() => useSuspenseQuery(buildListFlowsQuery()),
				{ wrapper: createWrapper({ queryClient }) },
			);

			await waitFor(() => {
				expect(result.current.data).toEqual([flow]);
			});
		});

		it("fetches paginated flows with custom search parameters", async () => {
			const flow = createFakeFlow();
			mockFetchFlowsAPI([flow]);

			const search = {
				name: "test",
				page: 1,
				limit: 10,
				sort: "NAME_ASC" as const,
				offset: 0,
			};

			const queryClient = new QueryClient();
			const { result } = renderHook(
				() => useSuspenseQuery(buildListFlowsQuery(search)),
				{ wrapper: createWrapper({ queryClient }) },
			);

			await waitFor(() => expect(result.current.isSuccess).toBe(true));
			expect(result.current.data).toEqual([flow]);
		});
	});

	describe("buildFLowDetailsQuery", () => {
		it("fetches flow details from the API", async () => {
			const flow = createFakeFlow();
			mockFetchFlowAPI(flow);

			const queryClient = new QueryClient();
			const { result } = renderHook(
				() => useSuspenseQuery(buildFLowDetailsQuery(flow.id)),
				{ wrapper: createWrapper({ queryClient }) },
			);

			await waitFor(() => expect(result.current.isSuccess).toBe(true));

			expect(result.current.data).toEqual(flow);
		});
	});

	describe("buildCountFlowsFilteredQuery", () => {
		it("fetches count of filtered flows from the API", async () => {
			const flow = createFakeFlow();
			mockFetchCountFlowsAPI(1);

			const queryClient = new QueryClient();
			const { result } = renderHook(
				() =>
					useSuspenseQuery(
						buildCountFlowsFilteredQuery({
							flows: {
								operator: "and_",
								name: { like_: flow.name },
							},
							offset: 0,
							sort: "CREATED_DESC",
						}),
					),
				{ wrapper: createWrapper({ queryClient }) },
			);

			await waitFor(() => expect(result.current.isSuccess).toBe(true));

			expect(result.current.data).toEqual(1);
		});
	});

	describe("useDeleteFlowById", () => {
		const mockFlow = createFakeFlow();

		it("invalidates cache and fetches updated value", async () => {
			const queryClient = new QueryClient();
			// Original cached value
			queryClient.setQueryData(queryKeyFactory.all(), [mockFlow]);

			// Updated fetch and cached value
			mockFetchFlowsAPI([mockFlow]);

			// Delete flow
			server.use(
				http.delete(buildApiUrl("/flows/:id"), () => {
					return HttpResponse.json({});
				}),
			);

			const { result: useListFLowsResult } = renderHook(
				() => useQuery(buildListFlowsQuery()),
				{ wrapper: createWrapper({ queryClient }) },
			);

			const { result: useDeleteFlowByIdResult } = renderHook(
				useDeleteFlowById,
				{ wrapper: createWrapper({ queryClient }) },
			);

			act(() => useDeleteFlowByIdResult.current.deleteFlow(mockFlow.id));

			mockFetchFlowsAPI([]);

			await waitFor(() => {
				return expect(useDeleteFlowByIdResult.current.isSuccess).toBe(true);
			});
			expect(useListFLowsResult.current.data).toHaveLength(0);
		});
	});
});
