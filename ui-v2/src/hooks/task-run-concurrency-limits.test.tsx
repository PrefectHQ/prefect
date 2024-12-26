import { components } from "@/api/prefect";
import { QueryClient, useSuspenseQuery } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { createWrapper, server } from "@tests/utils";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import {
	type TaskRunConcurrencyLimit,
	buildConcurrenyLimitDetailsActiveRunsQuery,
	queryKeyFactory,
	useCreateTaskRunConcurrencyLimit,
	useDeleteTaskRunConcurrencyLimit,
	useGetTaskRunConcurrencyLimit,
	useListTaskRunConcurrencyLimits,
	useResetTaskRunConcurrencyLimitTag,
} from "./task-run-concurrency-limits";

describe("task run concurrency limits hooks", () => {
	const seedData = () => [
		{
			id: "0",
			created: "2021-01-01T00:00:00Z",
			updated: "2021-01-01T00:00:00Z",
			tag: "my tag 0",
			concurrency_limit: 1,
			active_slots: ["task_0"],
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
	const seedData = () => ({
		id: "0",
		created: "2021-01-01T00:00:00Z",
		updated: "2021-01-01T00:00:00Z",
		tag: "my tag 0",
		concurrency_limit: 1,
		active_slots: ["task_0"],
	});

	const MOCK_TASK_RUNS: Array<components["schemas"]["TaskRun"]> = [
		{
			id: "task_0",
			created: "2024-12-18T19:07:44.837299Z",
			updated: "2024-12-18T19:07:45.019000Z",
			name: "hello-task-a0c",
			flow_run_id: "3f1093f1-c349-47f1-becf-111999ac9351",
			task_key: "say_hello-6b199e75",
			dynamic_key: "a0c05e3b-4129-4e6d-bcf9-8b6d289aa4c0",
			cache_key: null,
			cache_expiration: null,
			task_version: null,
			empirical_policy: {
				max_retries: 0,
				retry_delay_seconds: 0,
				retries: 0,
				retry_delay: 0,
				retry_jitter_factor: null,
			},
			tags: ["tag1", "test1", "onboarding", "test", "test2"],
			labels: {},
			state_id: "050b3aa3-c085-44da-bada-a6a239ca617b",
			task_inputs: {
				name: [],
			},
			state_type: "RUNNING",
			state_name: "Running",
			run_count: 1,
			flow_run_run_count: 1,
			expected_start_time: "2024-12-18T19:07:44.786401Z",
			next_scheduled_start_time: null,
			start_time: "2024-12-18T19:07:44.791572Z",
			end_time: null,
			total_run_time: 0,
			estimated_run_time: 0.901001,
			estimated_start_time_delta: 0.005171,
			state: {
				id: "050b3aa3-c085-44da-bada-a6a239ca617b",
				type: "RUNNING",
				name: "Running",
				timestamp: "2024-12-18T19:07:44.791572Z",
				message: "",
				data: null,
				state_details: {
					flow_run_id: "3f1093f1-c349-47f1-becf-111999ac9351",
					task_run_id: "652d0799-8e73-4b2d-8428-e60b070d0a97",
					child_flow_run_id: null,
					scheduled_time: null,
					cache_key: null,
					cache_expiration: null,
					deferred: false,
					untrackable_result: false,
					pause_timeout: null,
					pause_reschedule: false,
					pause_key: null,
					run_input_keyset: null,
					refresh_cache: null,
					retriable: null,
					transition_id: null,
					task_parameters_id: null,
				},
			},
		},
	];

	const MOCK_FLOW_RUNS: Array<components["schemas"]["FlowRun"]> = [
		{
			id: "3f1093f1-c349-47f1-becf-111999ac9351",
			created: "2024-12-18T19:07:44.726912Z",
			updated: "2024-12-18T19:07:49.473000Z",
			name: "authentic-cockatoo",
			flow_id: "5d8df4c9-d846-45b6-a5bc-55f0cb264bd2",
			state_id: "2298e945-6e3f-4def-ba97-1276937d3ef3",
			deployment_id: null,
			deployment_version: null,
			work_queue_id: null,
			work_queue_name: null,
			flow_version: "e22328439175aef5dfcba6aa44a4c392",
			parameters: {},
			idempotency_key: null,
			context: {},
			empirical_policy: {
				max_retries: 0,
				retry_delay_seconds: 0.0,
				retries: 0,
				retry_delay: 0,
				pause_keys: [],
				resuming: false,
				retry_type: null,
			},
			tags: [],
			labels: { "prefect.flow.id": "5d8df4c9-d846-45b6-a5bc-55f0cb264bd2" },
			parent_task_run_id: null,
			state_type: "COMPLETED",
			state_name: "Completed",
			run_count: 1,
			expected_start_time: "2024-12-18T19:07:44.726851Z",
			next_scheduled_start_time: null,
			start_time: "2024-12-18T19:07:44.750254Z",
			end_time: "2024-12-18T19:07:49.458237Z",
			total_run_time: 4.707983,
			estimated_run_time: 4.707983,
			estimated_start_time_delta: 0.023403,
			auto_scheduled: false,
			infrastructure_document_id: null,
			infrastructure_pid: null,
			created_by: null,
			state: {
				id: "2298e945-6e3f-4def-ba97-1276937d3ef3",
				type: "COMPLETED",
				name: "Completed",
				timestamp: "2024-12-18T19:07:49.458237Z",
				message: null,
				data: null,
				state_details: {
					flow_run_id: "3f1093f1-c349-47f1-becf-111999ac9351",
					task_run_id: null,
					child_flow_run_id: null,
					scheduled_time: null,
					cache_key: null,
					cache_expiration: null,
					deferred: null,
					untrackable_result: true,
					pause_timeout: null,
					pause_reschedule: false,
					pause_key: null,
					run_input_keyset: null,
					refresh_cache: null,
					retriable: null,
					transition_id: "c0ae12f9-d2a0-459a-8a2d-947fe7cebf46",
					task_parameters_id: null,
				},
			},
			job_variables: {},
		},
	];
	const MOCK_FLOW: components["schemas"]["Flow"] = {
		id: "5d8df4c9-d846-45b6-a5bc-55f0cb264bd2",
		created: "2024-12-10T21:50:18.315610Z",
		updated: "2024-12-10T21:50:18.315612Z",
		name: "hello-universe",
		tags: [],
		labels: {},
	};

	const mockFetchDetailsAPI = (data: TaskRunConcurrencyLimit) => {
		server.use(
			http.get("http://localhost:4200/api/concurrency_limits/:id", () => {
				return HttpResponse.json(data);
			}),
		);
	};

	const mockTaskRunsFiltersAPI = (
		data: Array<components["schemas"]["TaskRun"]>,
	) => {
		server.use(
			http.post("http://localhost:4200/api/task_runs/filter", () => {
				return HttpResponse.json(data);
			}),
		);
	};
	const mockFlowRunsFiltersAPI = (
		data: Array<components["schemas"]["FlowRun"]>,
	) => {
		server.use(
			http.post("http://localhost:4200/api/flow_runs/filter", () => {
				return HttpResponse.json(data);
			}),
		);
	};

	const mockGetFlowAPI = (data: components["schemas"]["Flow"]) => {
		server.use(
			http.get("http://localhost:4200/api/flows/:id", () => {
				return HttpResponse.json(data);
			}),
		);
	};

	/**
	 * Data Management:
	 * - Asserts fetch API to get details on the task run concurrency limit
	 * - Other APIs will not be fired because there are no active task runs
	 */
	it("will fetch only necessary data when there is no active task runs", async () => {
		const MOCK_DATA = { ...seedData(), active_slots: [] };
		const MOCK_ID = MOCK_DATA.id;
		mockFetchDetailsAPI(MOCK_DATA);

		const { result } = renderHook(
			() =>
				useSuspenseQuery(buildConcurrenyLimitDetailsActiveRunsQuery(MOCK_ID)),
			{ wrapper: createWrapper() },
		);

		// ------------ Assert
		await waitFor(() => expect(result.current.isSuccess).toBe(true));
		expect(result.current.data).toMatchObject({
			taskRunConcurrencyLimit: MOCK_DATA,
			activeTaskRuns: [],
		});
	});

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
		expect(result.current.data).toMatchObject({
			taskRunConcurrencyLimit: MOCK_DATA,
			activeTaskRuns: [
				{
					flow: MOCK_FLOW,
					flowRun: MOCK_FLOW_RUNS[0],
					taskRun: MOCK_TASK_RUNS[0],
				},
			],
		});
	});
});
