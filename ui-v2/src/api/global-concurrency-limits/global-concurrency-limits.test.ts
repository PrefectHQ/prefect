import { QueryClient } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";

import { createFakeGlobalConcurrencyLimit } from "@/mocks";
import {
	type GlobalConcurrencyLimit,
	queryKeyFactory,
	useCreateGlobalConcurrencyLimit,
	useDeleteGlobalConcurrencyLimit,
	useListGlobalConcurrencyLimits,
	useUpdateGlobalConcurrencyLimit,
} from "./global-concurrency-limits";

describe("global concurrency limits hooks", () => {
	const MOCK_DATA = createFakeGlobalConcurrencyLimit({
		id: "0",
	});
	const seedData = () => [MOCK_DATA];

	const mockFetchGlobalConcurrencyLimitsAPI = (
		globalConcurrencyLimits: Array<GlobalConcurrencyLimit>,
	) => {
		server.use(
			http.post(buildApiUrl("/v2/concurrency_limits/filter"), () => {
				return HttpResponse.json(globalConcurrencyLimits);
			}),
		);
	};

	const filter = {
		offset: 0,
	};

	/**
	 * Data Management:
	 * - Asserts global concurrency limit list data is fetched based on the APIs invoked for the hook
	 */
	it("is stores list data into the appropriate list query when using useQuery()", async () => {
		// ------------ Mock API requests when cache is empty
		const mockList = seedData();
		mockFetchGlobalConcurrencyLimitsAPI(mockList);

		// ------------ Initialize hooks to test
		const { result } = renderHook(
			() => useListGlobalConcurrencyLimits(filter),
			{ wrapper: createWrapper() },
		);

		// ------------ Assert
		await waitFor(() => expect(result.current.isSuccess).toBe(true));
		expect(result.current.data).toEqual(mockList);
	});

	/**
	 * Data Management:
	 * - Asserts global concurrency limit calls delete API and refetches updated list
	 */
	it("useDeleteGlobalConcurrencyLimit() invalidates cache and fetches updated value", async () => {
		const ID_TO_DELETE = "0";
		const queryClient = new QueryClient();

		// ------------ Mock API requests after queries are invalidated
		const mockData = seedData().filter((limit) => limit.id !== ID_TO_DELETE);
		mockFetchGlobalConcurrencyLimitsAPI(mockData);

		// ------------ Initialize cache
		queryClient.setQueryData(queryKeyFactory.list(filter), seedData());

		// ------------ Initialize hooks to test
		const { result: useListGlobalConcurrencyLimitsResult } = renderHook(
			() => useListGlobalConcurrencyLimits(filter),
			{ wrapper: createWrapper({ queryClient }) },
		);

		const { result: useDeleteGlobalConcurrencyLimitResult } = renderHook(
			useDeleteGlobalConcurrencyLimit,
			{ wrapper: createWrapper({ queryClient }) },
		);

		// ------------ Invoke mutation
		act(() =>
			useDeleteGlobalConcurrencyLimitResult.current.deleteGlobalConcurrencyLimit(
				ID_TO_DELETE,
			),
		);

		// ------------ Assert
		await waitFor(() =>
			expect(useDeleteGlobalConcurrencyLimitResult.current.isSuccess).toBe(
				true,
			),
		);
		expect(useListGlobalConcurrencyLimitsResult.current.data).toHaveLength(0);
	});

	/**
	 * Data Management:
	 * - Asserts create mutation API is called.
	 * - Upon create mutation API being called, cache is invalidated and asserts cache invalidation APIS are called
	 */
	it("useCreateGlobalConcurrencyLimit() invalidates cache and fetches updated value", async () => {
		const queryClient = new QueryClient();
		const MOCK_NEW_LIMIT_ID = "1";
		const MOCK_NEW_LIMIT = {
			active: true,
			active_slots: 0,
			denied_slots: 0,
			limit: 0,
			name: "global concurrency limit 1",
			slot_decay_per_second: 0,
		};

		// ------------ Mock API requests after queries are invalidated
		const NEW_LIMIT_DATA = createFakeGlobalConcurrencyLimit({
			id: MOCK_NEW_LIMIT_ID,
			...MOCK_NEW_LIMIT,
		});

		const mockData = [...seedData(), NEW_LIMIT_DATA];
		mockFetchGlobalConcurrencyLimitsAPI(mockData);

		// ------------ Initialize cache
		queryClient.setQueryData(queryKeyFactory.list(filter), seedData());

		// ------------ Initialize hooks to test
		const { result: useListGlobalConcurrencyLimitsResult } = renderHook(
			() => useListGlobalConcurrencyLimits(filter),
			{ wrapper: createWrapper({ queryClient }) },
		);
		const { result: useCreateGlobalConcurrencyLimitResult } = renderHook(
			useCreateGlobalConcurrencyLimit,
			{ wrapper: createWrapper({ queryClient }) },
		);

		// ------------ Invoke mutation
		act(() =>
			useCreateGlobalConcurrencyLimitResult.current.createGlobalConcurrencyLimit(
				MOCK_NEW_LIMIT,
			),
		);

		// ------------ Assert
		await waitFor(() =>
			expect(useCreateGlobalConcurrencyLimitResult.current.isSuccess).toBe(
				true,
			),
		);
		expect(useListGlobalConcurrencyLimitsResult.current.data).toHaveLength(2);
		const newLimit = useListGlobalConcurrencyLimitsResult.current.data?.find(
			(limit) => limit.id === MOCK_NEW_LIMIT_ID,
		);
		expect(newLimit).toMatchObject(NEW_LIMIT_DATA);
	});

	/**
	 * Data Management:
	 * - Asserts update mutation API is called.
	 * - Upon update mutation API being called, cache invalidates global concurrency limit details cache
	 */
	it("useUpdateGlobalConcurrencyLimit() invalidates cache and fetches updated value", async () => {
		const queryClient = new QueryClient();
		const MOCK_UPDATE_LIMIT_ID = "0";
		const UPDATED_LIMIT_BODY = {
			active: true,
			active_slots: 0,
			denied_slots: 0,
			limit: 0,
			name: "global concurrency limit updated",
			slot_decay_per_second: 0,
		};
		const UPDATED_LIMIT = {
			...UPDATED_LIMIT_BODY,
			id: MOCK_UPDATE_LIMIT_ID,
			created: "2021-01-01T00:00:00Z",
			updated: "2021-01-01T00:00:00Z",
		};

		// ------------ Mock API requests after queries are invalidated
		const mockData = seedData().map((limit) =>
			limit.id === MOCK_UPDATE_LIMIT_ID ? UPDATED_LIMIT : limit,
		);
		mockFetchGlobalConcurrencyLimitsAPI(mockData);

		// ------------ Initialize cache

		queryClient.setQueryData(queryKeyFactory.list(filter), seedData());

		// ------------ Initialize hooks to test
		const { result: useListGlobalConcurrencyLimitsResult } = renderHook(
			() => useListGlobalConcurrencyLimits(filter),
			{ wrapper: createWrapper({ queryClient }) },
		);

		const { result: useUpdateGlobalConcurrencyLimitResult } = renderHook(
			useUpdateGlobalConcurrencyLimit,
			{ wrapper: createWrapper({ queryClient }) },
		);

		// ------------ Invoke mutation
		act(() =>
			useUpdateGlobalConcurrencyLimitResult.current.updateGlobalConcurrencyLimit(
				{
					id_or_name: MOCK_UPDATE_LIMIT_ID,
					...UPDATED_LIMIT_BODY,
				},
			),
		);

		// ------------ Assert
		await waitFor(() =>
			expect(useUpdateGlobalConcurrencyLimitResult.current.isSuccess).toBe(
				true,
			),
		);

		const limit = useListGlobalConcurrencyLimitsResult.current.data?.find(
			(limit) => limit.id === MOCK_UPDATE_LIMIT_ID,
		);
		expect(limit).toMatchObject(UPDATED_LIMIT);
	});
});
