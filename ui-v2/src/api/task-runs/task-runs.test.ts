import { createFakeTaskRun } from "@/mocks";
import { QueryClient, useSuspenseQuery } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import {
	TaskRun,
	TaskRunsFilter,
	buildGetFlowRunsTaskRunsCountQuery,
	buildListTaskRunsQuery,
} from ".";

describe("task runs api", () => {
	const mockFetchTaskRunsAPI = (taskRuns: Array<TaskRun>) => {
		server.use(
			http.post(buildApiUrl("/task_runs/filter"), () => {
				return HttpResponse.json(taskRuns);
			}),
		);
	};

	describe("taskRunsQueryParams", () => {
		it("fetches paginated task runs with default parameters", async () => {
			const taskRun = createFakeTaskRun();
			mockFetchTaskRunsAPI([taskRun]);

			const queryClient = new QueryClient();
			const { result } = renderHook(
				() => useSuspenseQuery(buildListTaskRunsQuery()),
				{ wrapper: createWrapper({ queryClient }) },
			);

			await waitFor(() => {
				expect(result.current.data).toEqual([taskRun]);
			});
		});

		it("fetches paginated task runs with custom search parameters", async () => {
			const taskRun = createFakeTaskRun();
			mockFetchTaskRunsAPI([taskRun]);

			const filter: TaskRunsFilter = {
				offset: 0,
				limit: 10,
				sort: "ID_DESC" as const,
				task_runs: {
					operator: "and_" as const,
					name: { like_: "test-task-run" },
				},
			};

			const queryClient = new QueryClient();
			const { result } = renderHook(
				() => useSuspenseQuery(buildListTaskRunsQuery(filter)),
				{ wrapper: createWrapper({ queryClient }) },
			);

			await waitFor(() => expect(result.current.isSuccess).toBe(true));
			expect(result.current.data).toEqual([taskRun]);
		});

		it("uses the provided refetch interval", () => {
			const taskRun = createFakeTaskRun();
			mockFetchTaskRunsAPI([taskRun]);

			const customRefetchInterval = 60_000; // 1 minute

			const { refetchInterval } = buildListTaskRunsQuery(
				{ sort: "ID_DESC", offset: 0 },
				customRefetchInterval,
			);

			expect(refetchInterval).toBe(customRefetchInterval);
		});
	});

	describe("buildGetFlowRunsTaskRunsCountQuery", () => {
		const mockGetFlowRunsTaskRunsCountAPI = (
			response: Record<string, number>,
		) => {
			server.use(
				http.post(buildApiUrl("/ui/flow_runs/count-task-runs"), () => {
					return HttpResponse.json(response);
				}),
			);
		};

		it("fetches map of flow run ids vs query count ", async () => {
			const mockIds = ["0", "1", "2"];
			const mockResponse = { "0": 2, "1": 4, "2": 8 };
			mockGetFlowRunsTaskRunsCountAPI(mockResponse);

			const queryClient = new QueryClient();
			const { result } = renderHook(
				() => useSuspenseQuery(buildGetFlowRunsTaskRunsCountQuery(mockIds)),
				{ wrapper: createWrapper({ queryClient }) },
			);

			await waitFor(() => {
				expect(result.current.data).toEqual(mockResponse);
			});
		});
	});
});
