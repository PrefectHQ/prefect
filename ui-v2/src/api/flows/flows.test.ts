import type { components } from "@/api/prefect";
import { createFakeFlow } from "@/mocks";
import { QueryClient, useSuspenseQuery } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { buildListFlowsQuery } from ".";

type Flow = components["schemas"]["Flow"];

describe("flows api", () => {
	const mockFetchFlowsAPI = (flows: Array<Flow>) => {
		server.use(
			http.post(buildApiUrl("/flows/filter"), () => {
				return HttpResponse.json(flows);
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
});
