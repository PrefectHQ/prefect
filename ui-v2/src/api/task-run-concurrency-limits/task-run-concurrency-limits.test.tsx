import { QueryClient, useSuspenseQuery } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";
import type { components } from "@/api/prefect";
import {
	createFakeFlow,
	createFakeFlowRun,
	createFakeTaskRun,
	createFakeTaskRunConcurrencyLimit,
} from "@/mocks";
import {
	buildConcurrenyLimitDetailsActiveRunsQuery,
	queryKeyFactory,
	type TaskRunConcurrencyLimit,
	useCreateTaskRunConcurrencyLimit,
	useDeleteTaskRunConcurrencyLimit,
	useGetTaskRunConcurrencyLimit,
	useListTaskRunConcurrencyLimits,
	useResetTaskRunConcurrencyLimitTag,
} from "./task-run-concurrency-limits";

describe("task run concurrency limits hooks", () => {
	const MOCK_TASK_RUN_CONCURRENCY_LIMIT = createFakeTaskRunConcurrencyLimit({
		id: "0",
		tag: "my tag 0",
	});
	const seedData = () => [MOCK_TASK_RUN_CONCURRENCY_LIMIT];

	const mockFetchDetailsAPI = (data: TaskRunConcurrencyLimit) => {
		server.use(
			http.get(buildApiUrl("/concurrency_limits/:id"), () => {
				return HttpResponse.json(data);
			}),
		);
	};

	const mockFetchListAPI = (data: Array<TaskRunConcurrencyLimit>) => {
		server.use(
			http.post(buildApiUrl("/concurrency_limits/filter"), () => {
				return HttpResponse.json(data);
			}),
		);
	};

	const mockCreateAPI = (data: TaskRunConcurrencyLimit) => {
		server.use(
			http.post(buildApiUrl("/concurrency_limits/"), () => {
				return HttpResponse.json(data, { status: 201 });
			}),
		);
	};

	const filter = {
		offset: 0,
	};

	/**
	 * Data Management:
	 * - Asserts task run concurrency limit list data is fetched based on the APIs invoked for the hook
	 */
	it("useListTaskRunConcurrencyLimits() stores list data into the appropriate list query", async () => {
		// ------------ Mock API requests when cache is empty
		const mockList = seedData();
		mockFetchListAPI(seedData());

		// ------------ Initialize hooks to test
		const { result } = renderHook(
			() => useListTaskRunConcurrencyLimits(filter),
			{ wrapper: createWrapper({}) },
		);

		// ------------ Assert
		await waitFor(() => expect(result.current.isSuccess).toBe(true));
		expect(result.current.data).toEqual(mockList);
	});

	/**
	 * Data Management:
	 * - Asserts task run concurrency limit detail data is fetched based on the APIs invoked for the hook
	 */
	it("useGetTaskRunConcurrencyLimit() stores details data into the appropriate details query", async () => {
		// ------------ Mock API requests when cache is empty
		const mockData = seedData()[0];
		mockFetchDetailsAPI(mockData);

		// ------------ Initialize hooks to test
		const { result } = renderHook(
			() => useGetTaskRunConcurrencyLimit(mockData.id),
			{ wrapper: createWrapper({}) },
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
			() => useListTaskRunConcurrencyLimits(filter),
			{ wrapper: createWrapper({ queryClient }) },
		);

		const { result: useDeleteTaskRunConcurrencyLimitResult } = renderHook(
			useDeleteTaskRunConcurrencyLimit,
			{ wrapper: createWrapper({ queryClient }) },
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
		const MOCK_NEW_DATA = createFakeTaskRunConcurrencyLimit({
			id: MOCK_NEW_DATA_ID,
		});

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
			() => useListTaskRunConcurrencyLimits(filter),
			{ wrapper: createWrapper({ queryClient }) },
		);
		const { result: useCreateTaskRunConcurrencyLimitResult } = renderHook(
			useCreateTaskRunConcurrencyLimit,
			{ wrapper: createWrapper({ queryClient }) },
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
			() => useListTaskRunConcurrencyLimits(filter),
			{ wrapper: createWrapper({ queryClient }) },
		);
		const { result: useResetTaskRunConcurrencyLimitTagResults } = renderHook(
			useResetTaskRunConcurrencyLimitTag,
			{ wrapper: createWrapper({ queryClient }) },
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

describe("buildConcurrenyLimitDetailsActiveRunsQuery()", () => {
	const MOCK_DATA = createFakeTaskRunConcurrencyLimit({
		id: "0",
		tag: "my tag 0",
		concurrency_limit: 1,
		active_slots: ["task_0"],
	});
	const seedData = () => MOCK_DATA;
	const MOCK_TASK_RUNS = [
		createFakeTaskRun({ id: "task_0", flow_run_id: "flow_run_0" }),
	];
	const MOCK_FLOW_RUNS = [
		createFakeFlowRun({ id: "flow_run_0", flow_id: "flow_0" }),
	];
	const MOCK_FLOW = createFakeFlow({ id: "flow_0" });

	const mockFetchDetailsAPI = (data: TaskRunConcurrencyLimit) => {
		server.use(
			http.get(buildApiUrl("/concurrency_limits/:id"), () => {
				return HttpResponse.json(data);
			}),
		);
	};

	const mockTaskRunsFiltersAPI = (
		data: Array<components["schemas"]["TaskRun"]>,
	) => {
		server.use(
			http.post(buildApiUrl("/task_runs/filter"), () => {
				return HttpResponse.json(data);
			}),
		);
	};
	const mockFlowRunsFiltersAPI = (
		data: Array<components["schemas"]["FlowRun"]>,
	) => {
		server.use(
			http.post(buildApiUrl("/flow_runs/filter"), () => {
				return HttpResponse.json(data);
			}),
		);
	};

	const mockGetFlowAPI = (data: components["schemas"]["Flow"]) => {
		server.use(
			http.get(buildApiUrl("/flows/:id"), () => {
				return HttpResponse.json(data);
			}),
		);
	};

	/**
	 * Data Management:
	 * - Asserts waterfall of APIs will fire to get details on the task run concurrency limit
	 * - Other APIs will fire to get details on each task run, flow run associated with the task run, and overall flow details
	 */
	it("will fetch a necessary data for task runs", async () => {
		const MOCK_DATA = seedData();
		const MOCK_ID = MOCK_DATA.id;
		mockFetchDetailsAPI(MOCK_DATA);
		mockTaskRunsFiltersAPI(MOCK_TASK_RUNS);
		mockFlowRunsFiltersAPI(MOCK_FLOW_RUNS);
		mockGetFlowAPI(MOCK_FLOW);

		const { result } = renderHook(
			() =>
				useSuspenseQuery(buildConcurrenyLimitDetailsActiveRunsQuery(MOCK_ID)),
			{ wrapper: createWrapper() },
		);

		// ------------ Assert
		await waitFor(() => expect(result.current.isSuccess).toBe(true));
		expect(result.current.data.taskRunConcurrencyLimit).toMatchObject(
			MOCK_DATA,
		);
		const activeTaskRunsResult =
			await result.current.data.activeTaskRunsPromise;
		expect(activeTaskRunsResult).toEqual([
			{
				flow: MOCK_FLOW,
				flowRun: MOCK_FLOW_RUNS[0],
				taskRun: MOCK_TASK_RUNS[0],
			},
		]);
	});
});
