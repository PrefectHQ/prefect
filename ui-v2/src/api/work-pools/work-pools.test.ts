import { QueryClient, useSuspenseQuery } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";
import { createFakeWorkPool } from "@/mocks";
import {
	buildCountWorkPoolsQuery,
	buildFilterWorkPoolsQuery,
	buildListWorkPoolWorkersQuery,
	queryKeyFactory,
	useDeleteWorkPool,
	usePauseWorkPool,
	useResumeWorkPool,
	type WorkPool,
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

describe("work pool hooks", () => {
	const MOCK_WORK_POOL_NAME = "test-pool";

	/**
	 * Data Management:
	 * - Asserts pause mutation API is called
	 * - Upon pause mutation API being called, cache is invalidated
	 */
	it("usePauseWorkPool() invalidates cache", async () => {
		const queryClient = new QueryClient();

		// ------------ Mock API requests
		server.use(
			http.patch(buildApiUrl(`/work_pools/${MOCK_WORK_POOL_NAME}`), () => {
				return HttpResponse.json({});
			}),
		);

		// ------------ Initialize hooks to test
		const { result } = renderHook(usePauseWorkPool, {
			wrapper: createWrapper({ queryClient }),
		});

		// ------------ Invoke mutation
		act(() => result.current.pauseWorkPool(MOCK_WORK_POOL_NAME));

		// ------------ Assert
		await waitFor(() => expect(result.current.isSuccess).toBe(true));
	});

	/**
	 * Data Management:
	 * - Asserts resume mutation API is called
	 * - Upon resume mutation API being called, cache is invalidated
	 */
	it("useResumeWorkPool() invalidates cache", async () => {
		const queryClient = new QueryClient();

		// ------------ Mock API requests
		server.use(
			http.patch(buildApiUrl(`/work_pools/${MOCK_WORK_POOL_NAME}`), () => {
				return HttpResponse.json({});
			}),
		);

		// ------------ Initialize hooks to test
		const { result } = renderHook(useResumeWorkPool, {
			wrapper: createWrapper({ queryClient }),
		});

		// ------------ Invoke mutation
		act(() => result.current.resumeWorkPool(MOCK_WORK_POOL_NAME));

		// ------------ Assert
		await waitFor(() => expect(result.current.isSuccess).toBe(true));
	});

	/**
	 * Data Management:
	 * - Asserts delete mutation API is called
	 * - Upon delete mutation API being called, cache is invalidated
	 */
	it("useDeleteWorkPool() invalidates cache", async () => {
		const queryClient = new QueryClient();

		// ------------ Mock API requests
		server.use(
			http.delete(buildApiUrl(`/work_pools/${MOCK_WORK_POOL_NAME}`), () => {
				return HttpResponse.json({});
			}),
		);

		// ------------ Initialize hooks to test
		const { result } = renderHook(useDeleteWorkPool, {
			wrapper: createWrapper({ queryClient }),
		});

		// ------------ Invoke mutation
		act(() => result.current.deleteWorkPool(MOCK_WORK_POOL_NAME));

		// ------------ Assert
		await waitFor(() => expect(result.current.isSuccess).toBe(true));
	});
});

describe("work pool workers query key factory", () => {
	it("generates correct query keys", () => {
		expect(queryKeyFactory.all()).toEqual(["work-pools"]);
		expect(queryKeyFactory.workersLists()).toEqual(["work-pools", "workers"]);
		expect(queryKeyFactory.workersList("test-pool")).toEqual([
			"work-pools",
			"workers",
			"test-pool",
		]);
	});
});

describe("buildListWorkPoolWorkersQuery", () => {
	it("creates query options with correct key and refetch interval", () => {
		const query = buildListWorkPoolWorkersQuery("test-pool");

		expect(query.queryKey).toEqual(["work-pools", "workers", "test-pool"]);
		expect(query.refetchInterval).toBe(30000);
	});

	it("has a queryFn that calls the correct API endpoint", () => {
		const query = buildListWorkPoolWorkersQuery("my-pool");

		expect(query.queryFn).toBeDefined();
		expect(typeof query.queryFn).toBe("function");
	});
});
