import { createFakeWorkPool } from "@/mocks";
import { QueryClient, useSuspenseQuery } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import {
	type WorkPool,
	buildCountWorkPoolsQuery,
	buildFilterWorkPoolsQuery,
} from "./work-pools";

describe("work pools api", () => {
	const mockFetchWorkPoolsAPI = (workPools: Array<WorkPool>) => {
		server.use(
			http.post(buildApiUrl("/work_pools/filter"), () => {
				return HttpResponse.json(workPools);
			}),
			http.post(buildApiUrl("/work_pools/count"), () => {
				return HttpResponse.json(workPools.length);
			}),
		);
	};

	describe("buildFilterWorkPoolsQuery", () => {
		it("fetches filtered workpools", async () => {
			const workPool = createFakeWorkPool();
			mockFetchWorkPoolsAPI([workPool]);

			const queryClient = new QueryClient();
			const { result } = renderHook(
				() => useSuspenseQuery(buildFilterWorkPoolsQuery()),
				{ wrapper: createWrapper({ queryClient }) },
			);

			await waitFor(() => expect(result.current.isSuccess).toBe(true));
			expect(result.current.data).toEqual([workPool]);
		});
	});

	describe("buildCountWorkPoolsQuery", () => {
		it("fetches work pools count", async () => {
			mockFetchWorkPoolsAPI([createFakeWorkPool()]);

			const queryClient = new QueryClient();
			const { result } = renderHook(
				() => useSuspenseQuery(buildCountWorkPoolsQuery()),
				{ wrapper: createWrapper({ queryClient }) },
			);
			await waitFor(() => expect(result.current.isSuccess).toBe(true));
			expect(result.current.data).toBe(1);
		});
	});
});
