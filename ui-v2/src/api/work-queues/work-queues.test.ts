import { QueryClient, useSuspenseQuery } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";
import { createFakeWorkQueue } from "@/mocks";
import {
	buildFilterWorkPoolWorkQueuesQuery,
	buildFilterWorkQueuesQuery,
	buildWorkQueueDetailsQuery,
	type WorkQueue,
} from "./work-queues";

describe("work queues api", () => {
	const mockFetchWorkQueuesAPI = (workPools: Array<WorkQueue>) => {
		server.use(
			http.post(buildApiUrl("/work_queues/filter"), () => {
				return HttpResponse.json(workPools);
			}),
		);
	};

	describe("buildFilterWorkPoolsQuery", () => {
		it("fetches filtered workpools", async () => {
			const workQueue = createFakeWorkQueue();
			mockFetchWorkQueuesAPI([workQueue]);

			const queryClient = new QueryClient();
			const { result } = renderHook(
				() => useSuspenseQuery(buildFilterWorkQueuesQuery()),
				{ wrapper: createWrapper({ queryClient }) },
			);

			await waitFor(() => expect(result.current.isSuccess).toBe(true));
			expect(result.current.data).toEqual([workQueue]);
		});
	});

	describe("buildFilterWorkPoolWorkQueuesQuery", () => {
		const mockFetchWorkPoolWorkQueuesAPI = (workPools: Array<WorkQueue>) => {
			server.use(
				http.post(
					buildApiUrl("/work_pools/:work_pool_name/queues/filter"),
					() => {
						return HttpResponse.json(workPools);
					},
				),
			);
		};

		it("fetches filtered work queues from the parent work pool", async () => {
			const workQueue = createFakeWorkQueue({ work_pool_name: "my-work-pool" });
			mockFetchWorkPoolWorkQueuesAPI([workQueue]);

			const queryClient = new QueryClient();
			const { result } = renderHook(
				() =>
					useSuspenseQuery(
						buildFilterWorkPoolWorkQueuesQuery({
							work_pool_name: workQueue.work_pool_name,
						}),
					),
				{ wrapper: createWrapper({ queryClient }) },
			);

			await waitFor(() => expect(result.current.isSuccess).toBe(true));
			expect(result.current.data).toEqual([workQueue]);
		});
	});

	describe("buildWorkQueueDetailsQuery", () => {
		const mockGetWorkQueueAPI = (workQueue: WorkQueue) => {
			server.use(
				http.get(
					buildApiUrl("/work_pools/:work_pool_name/queues/:name"),
					() => {
						return HttpResponse.json(workQueue);
					},
				),
			);
		};

		it("fetches details about a work queue by name", async () => {
			const MOCK_WORK_QUEUE = createFakeWorkQueue({
				work_pool_name: "my-work-pool",
				name: "my-work-queue",
			});
			mockGetWorkQueueAPI(MOCK_WORK_QUEUE);

			const queryClient = new QueryClient();
			const { result } = renderHook(
				() =>
					useSuspenseQuery(
						buildWorkQueueDetailsQuery(
							MOCK_WORK_QUEUE.work_pool_name as string,
							MOCK_WORK_QUEUE.name,
						),
					),
				{ wrapper: createWrapper({ queryClient }) },
			);
			await waitFor(() => expect(result.current.isSuccess).toBe(true));
			expect(result.current.data).toEqual(MOCK_WORK_QUEUE);
		});
	});
});
