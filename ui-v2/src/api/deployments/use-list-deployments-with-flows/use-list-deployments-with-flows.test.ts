import { QueryClient } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";
import { createFakeDeployment, createFakeFlow } from "@/mocks";
import { useListDeploymentsWithFlows } from "./use-list-deployments-with-flows";

describe("buildPaginateDeploymentsWithFlowQuery", () => {
	it("fetches deployments pagination and flow filter APIs and joins data", async () => {
		const MOCK_DEPLOYMENTS = [
			createFakeDeployment({ id: "0", flow_id: "a" }),
			createFakeDeployment({ id: "1", flow_id: "a" }),
		];
		const MOCK_FLOW = createFakeFlow({ id: "a" });

		server.use(
			http.post(buildApiUrl("/deployments/paginate"), () => {
				return HttpResponse.json({
					results: MOCK_DEPLOYMENTS,
					count: MOCK_DEPLOYMENTS.length,
					page: 1,
					pages: 1,
					limit: 10,
				});
			}),
			http.post(buildApiUrl("/flows/filter"), () => {
				return HttpResponse.json([MOCK_FLOW]);
			}),
		);

		const queryClient = new QueryClient();

		const { result } = renderHook(useListDeploymentsWithFlows, {
			wrapper: createWrapper({ queryClient }),
		});

		await waitFor(() => {
			expect(result.current.status).toEqual("success");
		});

		const EXPECTED = MOCK_DEPLOYMENTS.map((deployment) => ({
			...deployment,
			flow: MOCK_FLOW,
		}));

		expect(EXPECTED).toEqual(result.current.data?.results);
	});
});
