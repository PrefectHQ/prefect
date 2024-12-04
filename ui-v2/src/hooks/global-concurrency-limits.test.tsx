import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import {
	type GlobalConcurrencyLimit,
	useGetGlobalConcurrencyLimit,
	useListGlobalConcurrencyLimits,
} from "./global-concurrency-limits";

import { server } from "../../tests/mocks/node";

describe("global concurrency limits hooks", () => {
	const seedGlobalConcurrencyLimits = () => [
		{
			id: "0",
			created: "2021-01-01T00:00:00Z",
			updated: "2021-01-01T00:00:00Z",
			active: false,
			name: "global concurrency limit 0",
			limit: 0,
			active_slots: 0,
			slot_decay_per_second: 0,
		},
	];

	const seedGlobalConcurrencyLimitDetails = () => ({
		id: "0",
		created: "2021-01-01T00:00:00Z",
		updated: "2021-01-01T00:00:00Z",
		active: false,
		name: "global concurrency limit 0",
		limit: 0,
		active_slots: 0,
		slot_decay_per_second: 0,
	});

	const mockFetchGlobalConcurrencyLimitsAPI = (
		globalConcurrencyLimits: Array<GlobalConcurrencyLimit>,
	) => {
		server.use(
			http.post(
				"http://localhost:4200/api/v2/concurrency_limits/filter",
				() => {
					return HttpResponse.json(globalConcurrencyLimits);
				},
			),
		);
	};

	const mockFetchGlobalConcurrencyLimitDetailsAPI = (
		globalConcurrencyLimit: GlobalConcurrencyLimit,
	) => {
		server.use(
			http.get(
				"http://localhost:4200/api/v2/concurrency_limits/:id_or_name",
				() => {
					return HttpResponse.json(globalConcurrencyLimit);
				},
			),
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
	 * - Asserts global concurrency limit list data is fetched based on the APIs invoked for the hook
	 */
	it("is stores list data into the appropriate list query when using useQuery()", async () => {
		// ------------ Mock API requests when cache is empty
		const mockList = seedGlobalConcurrencyLimits();
		mockFetchGlobalConcurrencyLimitsAPI(mockList);

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
	 * - Asserts global concurrency limit details data is fetched based on the APIs invoked for the hook
	 */
	it("is stores details data into the appropriate details query when using useQuery()", async () => {
		// ------------ Mock API requests when cache is empty
		const mockDetails = seedGlobalConcurrencyLimitDetails();
		mockFetchGlobalConcurrencyLimitDetailsAPI(mockDetails);

		// ------------ Initialize hooks to test
		const { result } = renderHook(
			() => useGetGlobalConcurrencyLimit(mockDetails.id),
			{ wrapper: createQueryWrapper({}) },
		);

		// ------------ Assert
		await waitFor(() => expect(result.current.isSuccess).toBe(true));
		expect(result.current.data).toEqual(mockDetails);
	});
});
