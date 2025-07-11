import { QueryClient } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";
import type { FlowRun } from "@/api/flow-runs";
import type { Flow } from "@/api/flows";
import { createFakeFlow, createFakeFlowRun } from "@/mocks";
import { usePaginateFlowRunswithFlows } from "./use-paginate-flow-runs-with-flows";

describe("usePaginateFlowRunswithFlows", () => {
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

	const mockFilterFlowsAPI = (flows: Array<Flow>) => {
		server.use(
			http.post(buildApiUrl("/flows/filter"), () => {
				return HttpResponse.json(flows);
			}),
		);
	};

	it("returns a pagination object with no results", async () => {
		// SETUP
		const queryClient = new QueryClient();

		mockPaginateFlowRunsAPI([]);

		// TEST
		const { result } = renderHook(
			() => usePaginateFlowRunswithFlows({ page: 1, sort: "NAME_ASC" }),
			{ wrapper: createWrapper({ queryClient }) },
		);

		await waitFor(() => expect(result.current.status).toEqual("success"));
		expect(result.current.data?.results).toHaveLength(0);
	});

	it("returns a pagination object with joined flows and flow runs", async () => {
		// SETUP
		const queryClient = new QueryClient();
		const MOCK_FLOW_RUN_0 = createFakeFlowRun({
			id: "0",
			flow_id: "flow-id-0",
		});
		const MOCK_FLOW_RUN_1 = createFakeFlowRun({
			id: "0",
			flow_id: "flow-id-0",
		});
		const MOCK_FLOW_RUN_2 = createFakeFlowRun({
			id: "0",
			flow_id: "flow-id-1",
		});
		const MOCK_FLOW_0 = createFakeFlow({ id: "flow-id-0" });
		const MOCK_FLOW_1 = createFakeFlow({ id: "flow-id-1" });

		const mockFlowRuns = [MOCK_FLOW_RUN_0, MOCK_FLOW_RUN_1, MOCK_FLOW_RUN_2];
		const mockFlows = [MOCK_FLOW_0, MOCK_FLOW_1];
		mockPaginateFlowRunsAPI(mockFlowRuns);
		mockFilterFlowsAPI(mockFlows);

		// TEST
		const { result } = renderHook(
			() => usePaginateFlowRunswithFlows({ page: 1, sort: "NAME_ASC" }),
			{ wrapper: createWrapper({ queryClient }) },
		);

		await waitFor(() => expect(result.current.status).toEqual("success"));

		// ASSERT
		const EXPECTED = [
			{
				...MOCK_FLOW_RUN_0,
				flow: MOCK_FLOW_0,
			},
			{
				...MOCK_FLOW_RUN_1,
				flow: MOCK_FLOW_0,
			},
			{
				...MOCK_FLOW_RUN_2,
				flow: MOCK_FLOW_1,
			},
		];

		expect(result.current.data?.results).toEqual(EXPECTED);
	});
});
