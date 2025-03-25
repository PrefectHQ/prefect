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
	buildWorkPoolDetailsQuery,
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

	describe("buildWorkPoolDetailsQuery", () => {
		const mockGetWorkPoolAPI = (workPool: WorkPool) => {
			server.use(
				http.get(buildApiUrl("/work_pools/:name"), () => {
					return HttpResponse.json(workPool);
				}),
			);
		};

		it("fetches details about a work pool by name", async () => {
			const MOCK_WORK_POOL = createFakeWorkPool({ name: "my-work-pool" });
			mockGetWorkPoolAPI(MOCK_WORK_POOL);

			const queryClient = new QueryClient();
			const { result } = renderHook(
				() => useSuspenseQuery(buildWorkPoolDetailsQuery(MOCK_WORK_POOL.name)),
				{ wrapper: createWrapper({ queryClient }) },
			);
			await waitFor(() => expect(result.current.isSuccess).toBe(true));
			expect(result.current.data).toEqual(MOCK_WORK_POOL);
		});
	});
});
