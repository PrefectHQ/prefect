import { QueryClient, useQuery, useSuspenseQuery } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";
import type { components } from "@/api/prefect";
import { createFakeFlow } from "@/mocks";
import {
	buildCountFlowsFilteredQuery,
	buildDeploymentsCountByFlowQuery,
	buildFLowDetailsQuery,
	buildListFlowsQuery,
	buildNextRunsByFlowQuery,
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

	describe("buildDeploymentsCountByFlowQuery", () => {
		const mockDeploymentsCountByFlow = (counts: Record<string, number>) => {
			server.use(
				http.post(buildApiUrl("/ui/flows/count-deployments"), () => {
					return HttpResponse.json(counts);
				}),
			);
		};

		it("fetches deployment counts by flow IDs", async () => {
			const flow1 = createFakeFlow();
			const flow2 = createFakeFlow();
			const mockCounts = { [flow1.id]: 3, [flow2.id]: 5 };
			mockDeploymentsCountByFlow(mockCounts);

			const queryClient = new QueryClient();
			const { result } = renderHook(
				() => useQuery(buildDeploymentsCountByFlowQuery([flow1.id, flow2.id])),
				{ wrapper: createWrapper({ queryClient }) },
			);

			await waitFor(() => expect(result.current.isSuccess).toBe(true));
			expect(result.current.data).toEqual(mockCounts);
		});

		it("returns empty object when no flow IDs provided", async () => {
			const queryClient = new QueryClient();
			const { result } = renderHook(
				() => useQuery(buildDeploymentsCountByFlowQuery([])),
				{ wrapper: createWrapper({ queryClient }) },
			);

			await waitFor(() => expect(result.current.fetchStatus).toBe("idle"));
			expect(result.current.data).toBeUndefined();
		});

		it("is disabled when enabled option is false", async () => {
			const flow = createFakeFlow();
			const queryClient = new QueryClient();
			const { result } = renderHook(
				() =>
					useQuery(
						buildDeploymentsCountByFlowQuery([flow.id], { enabled: false }),
					),
				{ wrapper: createWrapper({ queryClient }) },
			);

			await waitFor(() => expect(result.current.fetchStatus).toBe("idle"));
			expect(result.current.data).toBeUndefined();
		});
	});

	describe("buildNextRunsByFlowQuery", () => {
		const mockNextRunsByFlow = (
			runs: Record<string, components["schemas"]["SimpleNextFlowRun"] | null>,
		) => {
			server.use(
				http.post(buildApiUrl("/ui/flows/next-runs"), () => {
					return HttpResponse.json(runs);
				}),
			);
		};

		it("fetches next runs by flow IDs", async () => {
			const flow1 = createFakeFlow();
			const flow2 = createFakeFlow();
			const mockRuns = {
				[flow1.id]: {
					id: "run-1",
					flow_id: flow1.id,
					name: "next-run-1",
					state_name: "Scheduled",
					state_type: "SCHEDULED" as const,
					next_scheduled_start_time: new Date().toISOString(),
				},
				[flow2.id]: null,
			};
			mockNextRunsByFlow(mockRuns);

			const queryClient = new QueryClient();
			const { result } = renderHook(
				() => useQuery(buildNextRunsByFlowQuery([flow1.id, flow2.id])),
				{ wrapper: createWrapper({ queryClient }) },
			);

			await waitFor(() => expect(result.current.isSuccess).toBe(true));
			expect(result.current.data).toEqual(mockRuns);
		});

		it("returns empty object when no flow IDs provided", async () => {
			const queryClient = new QueryClient();
			const { result } = renderHook(
				() => useQuery(buildNextRunsByFlowQuery([])),
				{ wrapper: createWrapper({ queryClient }) },
			);

			await waitFor(() => expect(result.current.fetchStatus).toBe("idle"));
			expect(result.current.data).toBeUndefined();
		});

		it("is disabled when enabled option is false", async () => {
			const flow = createFakeFlow();
			const queryClient = new QueryClient();
			const { result } = renderHook(
				() => useQuery(buildNextRunsByFlowQuery([flow.id], { enabled: false })),
				{ wrapper: createWrapper({ queryClient }) },
			);

			await waitFor(() => expect(result.current.fetchStatus).toBe("idle"));
			expect(result.current.data).toBeUndefined();
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
