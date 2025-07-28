import { QueryClient, useSuspenseQuery } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { describe, expect, it, vi } from "vitest";
import { createFakeFlowRun } from "@/mocks";
import {
	buildFilterFlowRunsQuery,
	buildPaginateFlowRunsQuery,
	type FlowRun,
	queryKeyFactory,
	useDeleteFlowRun,
	useDeploymentCreateFlowRun,
} from ".";
import { useSetFlowRunState } from "./index";

describe("flow runs api", () => {
	const mockFetchFlowRunsAPI = (flowRuns: Array<FlowRun>) => {
		server.use(
			http.post(buildApiUrl("/flow_runs/filter"), () => {
				return HttpResponse.json(flowRuns);
			}),
		);
	};
	const mockCreateDeploymentFlowRunAPI = (flowRun: FlowRun) => {
		server.use(
			http.post(buildApiUrl("/deployments/:id/create_flow_run"), () => {
				return HttpResponse.json(flowRun);
			}),
		);
	};

	describe("flowRunsQueryParams", () => {
		it("fetches paginated flow runs with default parameters", async () => {
			const flowRun = createFakeFlowRun();
			mockFetchFlowRunsAPI([flowRun]);

			const queryClient = new QueryClient();
			const { result } = renderHook(
				() => useSuspenseQuery(buildFilterFlowRunsQuery()),
				{ wrapper: createWrapper({ queryClient }) },
			);

			await waitFor(() => {
				expect(result.current.data).toEqual([flowRun]);
			});
		});

		it("fetches paginated flow runs with custom search parameters", async () => {
			const flowRun = createFakeFlowRun();
			mockFetchFlowRunsAPI([flowRun]);

			const filter = {
				offset: 0,
				limit: 10,
				sort: "ID_DESC" as const,
				flow_runs: {
					operator: "and_" as const,
					name: { like_: "test-flow-run" },
				},
			};

			const queryClient = new QueryClient();
			const { result } = renderHook(
				() => useSuspenseQuery(buildFilterFlowRunsQuery(filter)),
				{ wrapper: createWrapper({ queryClient }) },
			);

			await waitFor(() => expect(result.current.isSuccess).toBe(true));
			expect(result.current.data).toEqual([flowRun]);
		});

		it("uses the provided refetch interval", () => {
			const flowRun = createFakeFlowRun();
			mockFetchFlowRunsAPI([flowRun]);

			const customRefetchInterval = 60_000; // 1 minute

			const { refetchInterval } = buildFilterFlowRunsQuery(
				{ sort: "ID_DESC", offset: 0 },
				customRefetchInterval,
			);

			expect(refetchInterval).toBe(customRefetchInterval);
		});
	});

	describe("buildPaginateFlowRunsQuery", () => {
		const mockPaginateFlowRunsAPI = (flowRuns: Array<FlowRun>) => {
			server.use(
				http.post(buildApiUrl("/flow_runs/paginate"), () => {
					return HttpResponse.json({
						limit: 10,
						page: 1,
						pages: 1,
						results: flowRuns,
						count: flowRuns.length,
					});
				}),
			);
		};

		it("fetches paginated flow runs", async () => {
			const mockFlowRuns = [
				createFakeFlowRun(),
				createFakeFlowRun(),
				createFakeFlowRun(),
			];
			mockPaginateFlowRunsAPI(mockFlowRuns);

			const queryClient = new QueryClient();
			const { result } = renderHook(
				() => useSuspenseQuery(buildPaginateFlowRunsQuery()),
				{ wrapper: createWrapper({ queryClient }) },
			);
			await waitFor(() => expect(result.current.isSuccess).toBe(true));

			expect(result.current.data.count).toEqual(3);
			expect(result.current.data.results).toEqual(mockFlowRuns);
		});
	});

	describe("useDeleteFlowRun", () => {
		it("invalidates cache and fetches updated value", async () => {
			const FILTER = {
				sort: "ID_DESC",
				offset: 0,
			} as const;
			const queryClient = new QueryClient();
			const EXISTING_CACHE = [
				createFakeFlowRun({ id: "0" }),
				createFakeFlowRun({ id: "1" }),
			];
			const MOCK_ID_TO_DELETE = "1";

			// ------------ Mock API requests after queries are invalidated
			const mockData = EXISTING_CACHE.filter(
				(data) => data.id !== MOCK_ID_TO_DELETE,
			);
			mockFetchFlowRunsAPI(mockData);

			// ------------ Initialize cache
			queryClient.setQueryData(queryKeyFactory.filter(FILTER), EXISTING_CACHE);

			// ------------ Initialize hooks to test
			const { result: useDeleteFlowRunResult } = renderHook(useDeleteFlowRun, {
				wrapper: createWrapper({ queryClient }),
			});

			const { result: useListFlowRunsResult } = renderHook(
				() => useSuspenseQuery(buildFilterFlowRunsQuery(FILTER)),
				{ wrapper: createWrapper({ queryClient }) },
			);

			// ------------ Invoke mutation
			act(() =>
				useDeleteFlowRunResult.current.deleteFlowRun(MOCK_ID_TO_DELETE),
			);

			// ------------ Assert
			await waitFor(() =>
				expect(useDeleteFlowRunResult.current.isSuccess).toBe(true),
			);

			expect(useListFlowRunsResult.current.data).toHaveLength(1);

			const newFlowRun = useListFlowRunsResult.current.data?.find(
				(flowRun) => flowRun.id === MOCK_ID_TO_DELETE,
			);
			expect(newFlowRun).toBeUndefined();
		});
	});
	describe("useDeploymentCreateFlowRun", () => {
		it("invalidates cache and fetches updated value", async () => {
			const FILTER = {
				sort: "ID_DESC",
				offset: 0,
			} as const;
			const queryClient = new QueryClient();
			const EXISTING_CACHE = [createFakeFlowRun(), createFakeFlowRun()];
			const MOCK_NEW_DATA_ID = "2";
			const NEW_FLOW_RUN_DATA = createFakeFlowRun({ id: MOCK_NEW_DATA_ID });

			// ------------ Mock API requests after queries are invalidated
			const mockData = [NEW_FLOW_RUN_DATA, ...EXISTING_CACHE];
			mockCreateDeploymentFlowRunAPI(NEW_FLOW_RUN_DATA);
			mockFetchFlowRunsAPI(mockData);

			// ------------ Initialize cache
			queryClient.setQueryData(queryKeyFactory.filter(FILTER), EXISTING_CACHE);

			// ------------ Initialize hooks to test
			const { result: useDeploymentCreateFlowRunResult } = renderHook(
				useDeploymentCreateFlowRun,
				{ wrapper: createWrapper({ queryClient }) },
			);

			const { result: useListFlowRunsResult } = renderHook(
				() => useSuspenseQuery(buildFilterFlowRunsQuery(FILTER)),
				{ wrapper: createWrapper({ queryClient }) },
			);

			// ------------ Invoke mutation
			act(() =>
				useDeploymentCreateFlowRunResult.current.createDeploymentFlowRun({
					id: MOCK_NEW_DATA_ID,
				}),
			);

			// ------------ Assert
			await waitFor(() =>
				expect(useDeploymentCreateFlowRunResult.current.isSuccess).toBe(true),
			);

			expect(useListFlowRunsResult.current.data).toHaveLength(3);

			const newFlowRun = useListFlowRunsResult.current.data?.find(
				(flowRun) => flowRun.id === MOCK_NEW_DATA_ID,
			);
			expect(newFlowRun).toMatchObject(NEW_FLOW_RUN_DATA);
		});
	});

	describe("useSetFlowRunState", () => {
		const flowRunId = "test-flow-run-id";
		const mockResponse = { state: { type: "FAILED" } };

		it("sets a flow run state", async () => {
			// Setup the mock server response
			server.use(
				http.post(buildApiUrl(`/flow_runs/${flowRunId}/set_state`), () => {
					return HttpResponse.json(mockResponse);
				}),
			);

			// Mock callbacks
			const onSuccess = vi.fn();
			const mutateOptions = { onSuccess };

			// Set up the hook
			const { result } = renderHook(() => useSetFlowRunState(), {
				wrapper: createWrapper(),
			});

			// Call the mutation
			act(() => {
				result.current.setFlowRunState(
					{
						id: flowRunId,
						state: {
							type: "FAILED",
							message: "Test message",
						},
						force: false,
					},
					mutateOptions,
				);
			});

			// Wait for the mutation to succeed with longer timeout
			await waitFor(() => expect(onSuccess).toHaveBeenCalledTimes(1), {
				timeout: 3000,
			});
		});

		it("handles errors when setting flow run state", async () => {
			// Setup the mock server error response
			server.use(
				http.post(buildApiUrl(`/flow_runs/${flowRunId}/set_state`), () => {
					return new HttpResponse(
						JSON.stringify({ detail: "Error setting flow run state" }),
						{ status: 400 },
					);
				}),
			);

			// Mock callbacks
			const onError = vi.fn();
			const mutateOptions = { onError };

			// Set up the hook
			const { result } = renderHook(() => useSetFlowRunState(), {
				wrapper: createWrapper(),
			});

			// Call the mutation
			act(() => {
				result.current.setFlowRunState(
					{
						id: flowRunId,
						state: {
							type: "FAILED",
							message: "Test message",
						},
						force: false,
					},
					mutateOptions,
				);
			});

			// Wait for the mutation to fail with longer timeout
			await waitFor(() => expect(onError).toHaveBeenCalledTimes(1), {
				timeout: 3000,
			});
		});
	});
});
