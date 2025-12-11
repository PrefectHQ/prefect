import { QueryClient, useQuery } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { describe, expect, it, vi } from "vitest";
import { createFakeTaskRun } from "@/mocks";
import type { TaskRun } from ".";
import {
	buildPaginateTaskRunsQuery,
	queryKeyFactory,
	useDeleteTaskRun,
	useSetTaskRunState,
} from ".";

describe("task runs api", () => {
	describe("buildPaginateTaskRunsQuery", () => {
		it("fetches paginated task runs with default parameters", async () => {
			const mockTaskRuns = [
				createFakeTaskRun({ id: "task-run-1", name: "Task Run 1" }),
				createFakeTaskRun({ id: "task-run-2", name: "Task Run 2" }),
			];

			server.use(
				http.post(buildApiUrl("/task_runs/paginate"), () => {
					return HttpResponse.json({
						results: mockTaskRuns,
						count: 2,
						pages: 1,
						page: 1,
						limit: 10,
					});
				}),
			);

			const { result } = renderHook(
				() => useQuery(buildPaginateTaskRunsQuery()),
				{
					wrapper: createWrapper(),
				},
			);

			await waitFor(() => expect(result.current.isSuccess).toBe(true));

			expect(result.current.data?.results).toHaveLength(2);
			expect(result.current.data?.results[0].id).toBe("task-run-1");
			expect(result.current.data?.results[1].id).toBe("task-run-2");
		});

		it("fetches paginated task runs with custom filter", async () => {
			const mockTaskRuns = [
				createFakeTaskRun({ id: "task-run-3", name: "Task Run 3" }),
			];

			server.use(
				http.post(buildApiUrl("/task_runs/paginate"), () => {
					return HttpResponse.json({
						results: mockTaskRuns,
						count: 1,
						pages: 1,
						page: 2,
						limit: 5,
					});
				}),
			);

			const { result } = renderHook(
				() =>
					useQuery(
						buildPaginateTaskRunsQuery({
							page: 2,
							limit: 5,
							sort: "EXPECTED_START_TIME_DESC",
						}),
					),
				{
					wrapper: createWrapper(),
				},
			);

			await waitFor(() => expect(result.current.isSuccess).toBe(true));

			expect(result.current.data?.results).toHaveLength(1);
			expect(result.current.data?.page).toBe(2);
			expect(result.current.data?.limit).toBe(5);
		});
	});

	describe("useSetTaskRunState", () => {
		const taskRunId = "test-task-run-id";
		const mockApiResponse = { state: { type: "FAILED", name: "Failed" } };

		it("calls the correct API endpoint and returns success", async () => {
			// Setup the mock server response
			server.use(
				http.post(buildApiUrl(`/task_runs/${taskRunId}/set_state`), () => {
					return HttpResponse.json(mockApiResponse);
				}),
			);

			// Mock callbacks
			const onSuccess = vi.fn();
			const onError = vi.fn();
			const onSettled = vi.fn();

			// Set up the hook
			const { result } = renderHook(() => useSetTaskRunState(), {
				wrapper: createWrapper(),
			});

			// Call the mutation
			act(() => {
				result.current.setTaskRunState(
					{
						id: taskRunId,
						state: { type: "FAILED", message: "Test failure" },
						force: true,
					},
					{ onSuccess, onError, onSettled },
				);
			});

			// Assertions
			await waitFor(() => expect(result.current.isSuccess).toBe(true));
			expect(onSuccess).toHaveBeenCalledTimes(1);
			expect(onError).not.toHaveBeenCalled();
			expect(onSettled).toHaveBeenCalledTimes(1);
		});

		it("invalidates queries on settled", async () => {
			const queryClient = new QueryClient();
			const invalidateQueriesSpy = vi.spyOn(queryClient, "invalidateQueries");

			server.use(
				http.post(buildApiUrl(`/task_runs/${taskRunId}/set_state`), () => {
					return HttpResponse.json(mockApiResponse);
				}),
			);

			const { result } = renderHook(() => useSetTaskRunState(), {
				wrapper: createWrapper({ queryClient }),
			});

			// Mock callback
			const onSettled = vi.fn();

			act(() => {
				result.current.setTaskRunState(
					{
						id: taskRunId,
						state: { type: "CANCELLED" },
						force: true,
					},
					{ onSettled },
				);
			});

			await waitFor(() => expect(onSettled).toHaveBeenCalledTimes(1));

			expect(invalidateQueriesSpy).toHaveBeenCalledWith({
				queryKey: queryKeyFactory.lists(),
			});
			expect(invalidateQueriesSpy).toHaveBeenCalledWith({
				queryKey: queryKeyFactory.detail(taskRunId),
			});
		});

		it("handles API error and rolls back optimistic update", async () => {
			const queryClient = new QueryClient();
			const initialData = createFakeTaskRun({
				id: taskRunId,
				state: { id: "initial-state-id", type: "PENDING", name: "Pending" },
			});
			const newState = { type: "RUNNING", name: "Running" } as const;
			const detailQueryKey = queryKeyFactory.detail(taskRunId);

			// Pre-populate cache
			queryClient.setQueryData<TaskRun>(detailQueryKey, initialData);

			// Setup mock server error response
			server.use(
				http.post(buildApiUrl(`/task_runs/${taskRunId}/set_state`), () => {
					return new HttpResponse(null, { status: 500 });
				}),
			);

			const setQueryDataSpy = vi.spyOn(queryClient, "setQueryData");
			const onError = vi.fn();

			const { result } = renderHook(() => useSetTaskRunState(), {
				wrapper: createWrapper({ queryClient }),
			});

			act(() => {
				result.current.setTaskRunState(
					{ id: taskRunId, state: newState, force: true },
					{ onError },
				);
			});

			await waitFor(() => expect(result.current.isError).toBe(true));

			// Check that original data was restored
			// Need to wait for the error handler to finish
			await waitFor(() => {
				expect(setQueryDataSpy).toHaveBeenCalledTimes(2); // Once for optimistic, once for rollback
				expect(setQueryDataSpy).toHaveBeenLastCalledWith(
					detailQueryKey,
					initialData,
				);
			});
			expect(onError).toHaveBeenCalledTimes(1);
			expect(result.current.error).toBeInstanceOf(Error);
		});
	});

	describe("useDeleteTaskRun", () => {
		// TODO: update this test when there's a list query to ensure the cache is invalidated
		it("calls the correct API endpoint and returns success", async () => {
			const taskRunId = "test-task-run-id";

			const { result } = renderHook(() => useDeleteTaskRun(), {
				wrapper: createWrapper(),
			});

			act(() => {
				result.current.deleteTaskRun({ id: taskRunId });
			});

			await waitFor(() => expect(result.current.isSuccess).toBe(true));
		});
	});
});
