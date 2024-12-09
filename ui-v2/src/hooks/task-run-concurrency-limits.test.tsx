import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import {
	type TaskRunConcurrencyLimit,
	queryKeyFactory,
	useCreateTaskRunConcurrencyLimit,
	useDeleteTaskRunConcurrencyLimit,
	useGetGlobalConcurrencyLimit,
	useListGlobalConcurrencyLimits,
	useResetTaskRunConcurrencyLimitTag,
} from "./task-run-concurrency-limits";

import { server } from "../../tests/mocks/node";

describe("task run concurrency limits hooks", () => {
	const seedData = () => [
		{
			id: "0",
			created: "2021-01-01T00:00:00Z",
			updated: "2021-01-01T00:00:00Z",
			tag: "my tag 0",
			concurrency_limit: 1,
			active_slots: [] as Array<string>,
		},
	];

	const mockFetchDetailsAPI = (data: TaskRunConcurrencyLimit) => {
		server.use(
			http.get("http://localhost:4200/api/concurrency_limits/:id", () => {
				return HttpResponse.json(data);
			}),
		);
	};

	const mockFetchListAPI = (data: Array<TaskRunConcurrencyLimit>) => {
		server.use(
			http.post("http://localhost:4200/api/concurrency_limits/filter", () => {
				return HttpResponse.json(data);
			}),
		);
	};

	const mockCreateAPI = (data: TaskRunConcurrencyLimit) => {
		server.use(
			http.post("http://localhost:4200/api/concurrency_limits/", () => {
				return HttpResponse.json(data, { status: 201 });
			}),
		);
	};
	const createQueryWrapper = ({ queryClient = new QueryClient() }) => {
		const QueryWrapper = ({ children }: { children: React.ReactNode }) => (
			<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
		);
		return QueryWrapper;
	};

	const filter = {
		offset: 0,
	};

	/**
	 * Data Management:
	 * - Asserts task run concurrency limit list data is fetched based on the APIs invoked for the hook
	 */
	it("useListGlobalConcurrencyLimits() stores list data into the appropriate list query", async () => {
		// ------------ Mock API requests when cache is empty
		const mockList = seedData();
		mockFetchListAPI(seedData());

		// ------------ Initialize hooks to test
		const { result } = renderHook(
			() => useListGlobalConcurrencyLimits(filter),
			{ wrapper: createQueryWrapper({}) },
		);

		// ------------ Assert
		await waitFor(() => expect(result.current.isSuccess).toBe(true));
		expect(result.current.data).toEqual(mockList);
	});

	/**
	 * Data Management:
	 * - Asserts task run concurrency limit detail data is fetched based on the APIs invoked for the hook
	 */
	it("useGetGlobalConcurrencyLimit() stores details data into the appropriate details query", async () => {
		// ------------ Mock API requests when cache is empty
		const mockData = seedData()[0];
		mockFetchDetailsAPI(mockData);

		// ------------ Initialize hooks to test
		const { result } = renderHook(
			() => useGetGlobalConcurrencyLimit(mockData.id),
			{ wrapper: createQueryWrapper({}) },
		);

		// ------------ Assert
		await waitFor(() => expect(result.current.isSuccess).toBe(true));
		expect(result.current.data).toMatchObject(mockData);
	});

	/**
	 * Data Management:
	 * - Asserts task run concurrency limit calls delete API and refetches updated list
	 */
	it("useDeleteTaskRunConcurrencyLimit() invalidates cache and fetches updated value", async () => {
		const ID_TO_DELETE = "0";
		const queryClient = new QueryClient();

		// ------------ Mock API requests after queries are invalidated
		const mockData = seedData().filter((limit) => limit.id !== ID_TO_DELETE);
		mockFetchListAPI(mockData);

		// ------------ Initialize cache
		queryClient.setQueryData(queryKeyFactory.list(filter), seedData());

		// ------------ Initialize hooks to test
		const { result: useListTaskRunConcurrencyLimitsResult } = renderHook(
			() => useListGlobalConcurrencyLimits(filter),
			{ wrapper: createQueryWrapper({ queryClient }) },
		);

		const { result: useDeleteTaskRunConcurrencyLimitResult } = renderHook(
			useDeleteTaskRunConcurrencyLimit,
			{ wrapper: createQueryWrapper({ queryClient }) },
		);

		// ------------ Invoke mutation
		act(() =>
			useDeleteTaskRunConcurrencyLimitResult.current.deleteTaskRunConcurrencyLimit(
				ID_TO_DELETE,
			),
		);

		// ------------ Assert
		await waitFor(() =>
			expect(useDeleteTaskRunConcurrencyLimitResult.current.isSuccess).toBe(
				true,
			),
		);
		expect(useListTaskRunConcurrencyLimitsResult.current.data).toHaveLength(0);
	});

	/**
	 * Data Management:
	 * - Asserts create mutation API is called.
	 * - Upon create mutation API being called, cache is invalidated and asserts cache invalidation APIS are called
	 */
	it("useCreateTaskRunConcurrencyLimit() invalidates cache and fetches updated value", async () => {
		const queryClient = new QueryClient();
		const MOCK_NEW_DATA_ID = "1";
		const MOCK_NEW_DATA = {
			tag: "my tag 1",
			concurrency_limit: 2,
			active_slots: [],
		};

		// ------------ Mock API requests after queries are invalidated
		const NEW_LIMIT_DATA = {
			...MOCK_NEW_DATA,
			id: MOCK_NEW_DATA_ID,
			created: "2021-01-01T00:00:00Z",
			updated: "2021-01-01T00:00:00Z",
		};

		const mockData = [...seedData(), NEW_LIMIT_DATA];
		mockFetchListAPI(mockData);
		mockCreateAPI(NEW_LIMIT_DATA);

		// ------------ Initialize cache
		queryClient.setQueryData(queryKeyFactory.list(filter), seedData());

		// ------------ Initialize hooks to test
		const { result: useListTaskRunConcurrencyLimitsResult } = renderHook(
			() => useListGlobalConcurrencyLimits(filter),
			{ wrapper: createQueryWrapper({ queryClient }) },
		);
		const { result: useCreateTaskRunConcurrencyLimitResult } = renderHook(
			useCreateTaskRunConcurrencyLimit,
			{ wrapper: createQueryWrapper({ queryClient }) },
		);

		// ------------ Invoke mutation
		act(() =>
			useCreateTaskRunConcurrencyLimitResult.current.createTaskRunConcurrencyLimit(
				MOCK_NEW_DATA,
			),
		);

		// ------------ Assert
		await waitFor(() =>
			expect(useCreateTaskRunConcurrencyLimitResult.current.isSuccess).toBe(
				true,
			),
		);
		expect(useListTaskRunConcurrencyLimitsResult.current.data).toHaveLength(2);
		const newLimit = useListTaskRunConcurrencyLimitsResult.current.data?.find(
			(limit) => limit.id === MOCK_NEW_DATA_ID,
		);
		expect(newLimit).toMatchObject(NEW_LIMIT_DATA);
	});
	/**
	 * Data Management:
	 * - Asserts reset mutation API is called.
	 * - Upon resetting active task run mutation API being called, cache is invalidated and asserts cache invalidation APIS are called
	 */
	it("useCreateTaskRunConcurrencyLimit() invalidates cache and fetches updated value", async () => {
		const queryClient = new QueryClient();
		const MOCK_TAG_NAME = "my tag 0";

		// ------------ Mock API requests after queries are invalidated
		const mockData = seedData().map((limit) =>
			limit.tag === MOCK_TAG_NAME
				? {
						...limit,
						active_slots: [],
					}
				: limit,
		);

		mockFetchListAPI(mockData);

		// ------------ Initialize cache
		queryClient.setQueryData(queryKeyFactory.list(filter), seedData());

		// ------------ Initialize hooks to test
		const { result: useListTaskRunConcurrencyLimitsResult } = renderHook(
			() => useListGlobalConcurrencyLimits(filter),
			{ wrapper: createQueryWrapper({ queryClient }) },
		);
		const { result: useResetTaskRunConcurrencyLimitTagResults } = renderHook(
			useResetTaskRunConcurrencyLimitTag,
			{ wrapper: createQueryWrapper({ queryClient }) },
		);

		// ------------ Invoke mutation
		act(() =>
			useResetTaskRunConcurrencyLimitTagResults.current.resetTaskRunConcurrencyLimitTag(
				MOCK_TAG_NAME,
			),
		);

		// ------------ Assert
		await waitFor(() =>
			expect(useResetTaskRunConcurrencyLimitTagResults.current.isSuccess).toBe(
				true,
			),
		);
		const limit = useListTaskRunConcurrencyLimitsResult.current.data?.find(
			(limit) => limit.tag === MOCK_TAG_NAME,
		);
		expect(limit?.active_slots).toHaveLength(0);
	});
});
