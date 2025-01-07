import type { components } from "@/api/prefect";
import { createFakeFlowRun } from "@/mocks";
import { QueryClient, useSuspenseQuery } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { buildListFlowRunsQuery } from ".";

type FlowRun = components["schemas"]["FlowRun"];

describe("flow runs api", () => {
	const mockFetchFlowRunsAPI = (flowRuns: Array<FlowRun>) => {
		server.use(
			http.post(buildApiUrl("/flow_runs/filter"), () => {
				return HttpResponse.json(flowRuns);
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
});
