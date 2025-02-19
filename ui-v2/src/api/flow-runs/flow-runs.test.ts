import type { components } from "@/api/prefect";
import { createFakeFlowRun } from "@/mocks";
import { QueryClient, useSuspenseQuery } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import {
	buildListFlowRunsQuery,
	queryKeyFactory,
	useDeleteFlowRun,
	useDeploymentCreateFlowRun,
} from ".";

type FlowRun = components["schemas"]["FlowRun"];

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
				() => useSuspenseQuery(buildListFlowRunsQuery()),
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
				() => useSuspenseQuery(buildListFlowRunsQuery(filter)),
				{ wrapper: createWrapper({ queryClient }) },
			);

			await waitFor(() => expect(result.current.isSuccess).toBe(true));
			expect(result.current.data).toEqual([flowRun]);
		});

		it("uses the provided refetch interval", () => {
			const flowRun = createFakeFlowRun();
			mockFetchFlowRunsAPI([flowRun]);

			const customRefetchInterval = 60_000; // 1 minute

			const { refetchInterval } = buildListFlowRunsQuery(
				{ sort: "ID_DESC", offset: 0 },
				customRefetchInterval,
			);

			expect(refetchInterval).toBe(customRefetchInterval);
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
			queryClient.setQueryData(queryKeyFactory.list(FILTER), EXISTING_CACHE);

			// ------------ Initialize hooks to test
			const { result: useDeleteFlowRunResult } = renderHook(useDeleteFlowRun, {
				wrapper: createWrapper({ queryClient }),
			});

			const { result: useListFlowRunsResult } = renderHook(
				() => useSuspenseQuery(buildListFlowRunsQuery(FILTER)),
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
			queryClient.setQueryData(queryKeyFactory.list(FILTER), EXISTING_CACHE);

			// ------------ Initialize hooks to test
			const { result: useDeploymentCreateFlowRunResult } = renderHook(
				useDeploymentCreateFlowRun,
				{ wrapper: createWrapper({ queryClient }) },
			);

			const { result: useListFlowRunsResult } = renderHook(
				() => useSuspenseQuery(buildListFlowRunsQuery(FILTER)),
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
});
