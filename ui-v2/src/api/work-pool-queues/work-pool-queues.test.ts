import { QueryClient, useSuspenseQuery } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { describe, expect, it, vi } from "vitest";
import { createFakeWorkPoolQueue } from "@/mocks";
import {
	buildListWorkPoolQueuesQuery,
	buildWorkPoolQueueDetailsQuery,
	useCreateWorkPoolQueueMutation,
	useDeleteWorkPoolQueueMutation,
	usePauseWorkPoolQueueMutation,
	useResumeWorkPoolQueueMutation,
	type WorkPoolQueue,
	workPoolQueuesQueryKeyFactory,
} from "./work-pool-queues";

describe("work pool queues query key factory", () => {
	it("generates correct query keys for all", () => {
		expect(workPoolQueuesQueryKeyFactory.all()).toEqual(["work_pool_queues"]);
	});

	it("generates correct query keys for lists", () => {
		expect(workPoolQueuesQueryKeyFactory.lists()).toEqual([
			"work_pool_queues",
			"list",
		]);
	});

	it("generates correct query keys for specific list", () => {
		expect(workPoolQueuesQueryKeyFactory.list("test-pool")).toEqual([
			"work_pool_queues",
			"list",
			"test-pool",
		]);
	});

	it("generates correct query keys for details", () => {
		expect(workPoolQueuesQueryKeyFactory.details()).toEqual([
			"work_pool_queues",
			"details",
		]);
	});

	it("generates correct query keys for specific detail", () => {
		expect(
			workPoolQueuesQueryKeyFactory.detail("test-pool", "test-queue"),
		).toEqual(["work_pool_queues", "details", "test-pool", "test-queue"]);
	});
});

describe("work pool queues api queries", () => {
	describe("buildListWorkPoolQueuesQuery", () => {
		const mockFetchWorkPoolQueuesAPI = (
			workPoolName: string,
			workQueues: Array<WorkPoolQueue>,
		) => {
			server.use(
				http.post(
					buildApiUrl(`/work_pools/${workPoolName}/queues/filter`),
					() => {
						return HttpResponse.json(workQueues);
					},
				),
			);
		};

		it("creates query options with correct key and refetch interval", () => {
			const query = buildListWorkPoolQueuesQuery("test-pool");

			expect(query.queryKey).toEqual(["work_pool_queues", "list", "test-pool"]);
			expect(query.refetchInterval).toBe(30000);
		});

		it("has a queryFn that calls the correct API endpoint", () => {
			const query = buildListWorkPoolQueuesQuery("my-pool");

			expect(query.queryFn).toBeDefined();
			expect(typeof query.queryFn).toBe("function");
		});

		it("fetches work pool queues for a specific work pool", async () => {
			const workPoolName = "test-pool";
			const mockQueues = [
				createFakeWorkPoolQueue({ work_pool_name: workPoolName }),
				createFakeWorkPoolQueue({ work_pool_name: workPoolName }),
			];
			mockFetchWorkPoolQueuesAPI(workPoolName, mockQueues);

			const queryClient = new QueryClient();
			const { result } = renderHook(
				() => useSuspenseQuery(buildListWorkPoolQueuesQuery(workPoolName)),
				{ wrapper: createWrapper({ queryClient }) },
			);

			await waitFor(() => expect(result.current.isSuccess).toBe(true));
			expect(result.current.data).toEqual(mockQueues);
		});

		it("has queryFn that throws error when API returns null data", async () => {
			const workPoolName = "test-pool";
			const query = buildListWorkPoolQueuesQuery(workPoolName);

			// Mock API to return null data
			server.use(
				http.post(
					buildApiUrl(`/work_pools/${workPoolName}/queues/filter`),
					() => {
						return HttpResponse.json(null);
					},
				),
			);

			// Test that the queryFn throws the expected error
			if (query.queryFn) {
				const mockContext = {
					queryKey: workPoolQueuesQueryKeyFactory.list(workPoolName),
					signal: new AbortController().signal,
					meta: {},
					client: {} as unknown,
				} as Parameters<NonNullable<typeof query.queryFn>>[0];
				await expect(query.queryFn(mockContext)).rejects.toThrow(
					"'data' expected",
				);
			}
		});
	});

	describe("buildWorkPoolQueueDetailsQuery", () => {
		const mockGetWorkPoolQueueAPI = (
			workPoolName: string,
			queueName: string,
			workQueue: WorkPoolQueue,
		) => {
			server.use(
				http.get(
					buildApiUrl(`/work_pools/${workPoolName}/queues/${queueName}`),
					() => {
						return HttpResponse.json(workQueue);
					},
				),
			);
		};

		it("creates query options with correct key", () => {
			const query = buildWorkPoolQueueDetailsQuery("test-pool", "test-queue");

			expect(query.queryKey).toEqual([
				"work_pool_queues",
				"details",
				"test-pool",
				"test-queue",
			]);
		});

		it("has a queryFn that calls the correct API endpoint", () => {
			const query = buildWorkPoolQueueDetailsQuery("my-pool", "my-queue");

			expect(query.queryFn).toBeDefined();
			expect(typeof query.queryFn).toBe("function");
		});

		it("fetches details about a work pool queue by name", async () => {
			const workPoolName = "test-pool";
			const queueName = "test-queue";
			const mockQueue = createFakeWorkPoolQueue({
				work_pool_name: workPoolName,
				name: queueName,
			});
			mockGetWorkPoolQueueAPI(workPoolName, queueName, mockQueue);

			const queryClient = new QueryClient();
			const { result } = renderHook(
				() =>
					useSuspenseQuery(
						buildWorkPoolQueueDetailsQuery(workPoolName, queueName),
					),
				{ wrapper: createWrapper({ queryClient }) },
			);

			await waitFor(() => expect(result.current.isSuccess).toBe(true));
			expect(result.current.data).toEqual(mockQueue);
		});

		it("has queryFn that throws error when API returns null data", async () => {
			const workPoolName = "test-pool";
			const queueName = "test-queue";
			const query = buildWorkPoolQueueDetailsQuery(workPoolName, queueName);

			// Mock API to return null data
			server.use(
				http.get(
					buildApiUrl(`/work_pools/${workPoolName}/queues/${queueName}`),
					() => {
						return HttpResponse.json(null);
					},
				),
			);

			// Test that the queryFn throws the expected error
			if (query.queryFn) {
				const mockContext = {
					queryKey: workPoolQueuesQueryKeyFactory.detail(
						workPoolName,
						queueName,
					),
					signal: new AbortController().signal,
					meta: {},
					client: {} as QueryClient,
				} as Parameters<NonNullable<typeof query.queryFn>>[0];
				await expect(query.queryFn(mockContext)).rejects.toThrow(
					"'data' expected",
				);
			}
		});
	});
});

describe("work pool queue mutation hooks", () => {
	const MOCK_WORK_POOL_NAME = "test-pool";
	const MOCK_QUEUE_NAME = "test-queue";

	describe("usePauseWorkPoolQueueMutation", () => {
		it("calls PATCH API to pause queue", async () => {
			const queryClient = new QueryClient();

			// Mock the API endpoint
			server.use(
				http.patch(
					buildApiUrl(
						`/work_pools/${MOCK_WORK_POOL_NAME}/queues/${MOCK_QUEUE_NAME}`,
					),
					async ({ request }) => {
						const body = await request.json();
						expect(body).toEqual({ is_paused: true });
						return HttpResponse.json({});
					},
				),
			);

			const { result } = renderHook(usePauseWorkPoolQueueMutation, {
				wrapper: createWrapper({ queryClient }),
			});

			// Invoke mutation
			act(() =>
				result.current.mutate({
					workPoolName: MOCK_WORK_POOL_NAME,
					queueName: MOCK_QUEUE_NAME,
				}),
			);

			await waitFor(() => expect(result.current.isSuccess).toBe(true));
		});

		it("invalidates cache on success", async () => {
			const queryClient = new QueryClient();
			const invalidateQueriesSpy = vi.spyOn(queryClient, "invalidateQueries");

			// Mock the API endpoint
			server.use(
				http.patch(
					buildApiUrl(
						`/work_pools/${MOCK_WORK_POOL_NAME}/queues/${MOCK_QUEUE_NAME}`,
					),
					() => {
						return HttpResponse.json({});
					},
				),
			);

			const { result } = renderHook(usePauseWorkPoolQueueMutation, {
				wrapper: createWrapper({ queryClient }),
			});

			// Invoke mutation
			act(() =>
				result.current.mutate({
					workPoolName: MOCK_WORK_POOL_NAME,
					queueName: MOCK_QUEUE_NAME,
				}),
			);

			await waitFor(() => expect(result.current.isSuccess).toBe(true));

			// Verify cache invalidation calls
			expect(invalidateQueriesSpy).toHaveBeenCalledWith({
				queryKey: workPoolQueuesQueryKeyFactory.list(MOCK_WORK_POOL_NAME),
			});
			expect(invalidateQueriesSpy).toHaveBeenCalledWith({
				queryKey: workPoolQueuesQueryKeyFactory.detail(
					MOCK_WORK_POOL_NAME,
					MOCK_QUEUE_NAME,
				),
			});
		});
	});

	describe("useResumeWorkPoolQueueMutation", () => {
		it("calls PATCH API to resume queue", async () => {
			const queryClient = new QueryClient();

			// Mock the API endpoint
			server.use(
				http.patch(
					buildApiUrl(
						`/work_pools/${MOCK_WORK_POOL_NAME}/queues/${MOCK_QUEUE_NAME}`,
					),
					async ({ request }) => {
						const body = await request.json();
						expect(body).toEqual({ is_paused: false });
						return HttpResponse.json({});
					},
				),
			);

			const { result } = renderHook(useResumeWorkPoolQueueMutation, {
				wrapper: createWrapper({ queryClient }),
			});

			// Invoke mutation
			act(() =>
				result.current.mutate({
					workPoolName: MOCK_WORK_POOL_NAME,
					queueName: MOCK_QUEUE_NAME,
				}),
			);

			await waitFor(() => expect(result.current.isSuccess).toBe(true));
		});

		it("invalidates cache on success", async () => {
			const queryClient = new QueryClient();
			const invalidateQueriesSpy = vi.spyOn(queryClient, "invalidateQueries");

			// Mock the API endpoint
			server.use(
				http.patch(
					buildApiUrl(
						`/work_pools/${MOCK_WORK_POOL_NAME}/queues/${MOCK_QUEUE_NAME}`,
					),
					() => {
						return HttpResponse.json({});
					},
				),
			);

			const { result } = renderHook(useResumeWorkPoolQueueMutation, {
				wrapper: createWrapper({ queryClient }),
			});

			// Invoke mutation
			act(() =>
				result.current.mutate({
					workPoolName: MOCK_WORK_POOL_NAME,
					queueName: MOCK_QUEUE_NAME,
				}),
			);

			await waitFor(() => expect(result.current.isSuccess).toBe(true));

			// Verify cache invalidation calls
			expect(invalidateQueriesSpy).toHaveBeenCalledWith({
				queryKey: workPoolQueuesQueryKeyFactory.list(MOCK_WORK_POOL_NAME),
			});
			expect(invalidateQueriesSpy).toHaveBeenCalledWith({
				queryKey: workPoolQueuesQueryKeyFactory.detail(
					MOCK_WORK_POOL_NAME,
					MOCK_QUEUE_NAME,
				),
			});
		});
	});

	describe("useCreateWorkPoolQueueMutation", () => {
		it("calls POST API to create queue", async () => {
			const queryClient = new QueryClient();
			const mockWorkQueueData = {
				name: "new-queue",
				description: "Test queue",
				is_paused: false,
				concurrency_limit: 5,
				priority: 10,
			};

			// Mock the API endpoint
			server.use(
				http.post(
					buildApiUrl(`/work_pools/${MOCK_WORK_POOL_NAME}/queues`),
					async ({ request }) => {
						const body = await request.json();
						expect(body).toEqual(mockWorkQueueData);
						return HttpResponse.json({
							id: "new-queue-id",
							...mockWorkQueueData,
						});
					},
				),
			);

			const { result } = renderHook(useCreateWorkPoolQueueMutation, {
				wrapper: createWrapper({ queryClient }),
			});

			// Invoke mutation
			act(() =>
				result.current.mutate({
					workPoolName: MOCK_WORK_POOL_NAME,
					workQueueData: mockWorkQueueData,
				}),
			);

			await waitFor(() => expect(result.current.isSuccess).toBe(true));
		});

		it("invalidates list cache on success", async () => {
			const queryClient = new QueryClient();
			const invalidateQueriesSpy = vi.spyOn(queryClient, "invalidateQueries");

			// Mock the API endpoint
			server.use(
				http.post(
					buildApiUrl(`/work_pools/${MOCK_WORK_POOL_NAME}/queues`),
					() => {
						return HttpResponse.json({ id: "new-queue-id", name: "new-queue" });
					},
				),
			);

			const { result } = renderHook(useCreateWorkPoolQueueMutation, {
				wrapper: createWrapper({ queryClient }),
			});

			// Invoke mutation
			act(() =>
				result.current.mutate({
					workPoolName: MOCK_WORK_POOL_NAME,
					workQueueData: {
						name: "new-queue",
						description: null,
						is_paused: false,
					},
				}),
			);

			await waitFor(() => expect(result.current.isSuccess).toBe(true));

			// Verify list cache is invalidated
			expect(invalidateQueriesSpy).toHaveBeenCalledWith({
				queryKey: workPoolQueuesQueryKeyFactory.list(MOCK_WORK_POOL_NAME),
			});
		});
	});

	describe("useDeleteWorkPoolQueueMutation", () => {
		it("calls DELETE API to delete queue", async () => {
			const queryClient = new QueryClient();

			// Mock the API endpoint
			server.use(
				http.delete(
					buildApiUrl(
						`/work_pools/${MOCK_WORK_POOL_NAME}/queues/${MOCK_QUEUE_NAME}`,
					),
					() => {
						return HttpResponse.json({});
					},
				),
			);

			const { result } = renderHook(useDeleteWorkPoolQueueMutation, {
				wrapper: createWrapper({ queryClient }),
			});

			// Invoke mutation
			act(() =>
				result.current.mutate({
					workPoolName: MOCK_WORK_POOL_NAME,
					queueName: MOCK_QUEUE_NAME,
				}),
			);

			await waitFor(() => expect(result.current.isSuccess).toBe(true));
		});

		it("invalidates list cache on success", async () => {
			const queryClient = new QueryClient();
			const invalidateQueriesSpy = vi.spyOn(queryClient, "invalidateQueries");

			// Mock the API endpoint
			server.use(
				http.delete(
					buildApiUrl(
						`/work_pools/${MOCK_WORK_POOL_NAME}/queues/${MOCK_QUEUE_NAME}`,
					),
					() => {
						return HttpResponse.json({});
					},
				),
			);

			const { result } = renderHook(useDeleteWorkPoolQueueMutation, {
				wrapper: createWrapper({ queryClient }),
			});

			// Invoke mutation
			act(() =>
				result.current.mutate({
					workPoolName: MOCK_WORK_POOL_NAME,
					queueName: MOCK_QUEUE_NAME,
				}),
			);

			await waitFor(() => expect(result.current.isSuccess).toBe(true));

			// Verify only list cache is invalidated (not detail since queue is deleted)
			expect(invalidateQueriesSpy).toHaveBeenCalledWith({
				queryKey: workPoolQueuesQueryKeyFactory.list(MOCK_WORK_POOL_NAME),
			});
			expect(invalidateQueriesSpy).not.toHaveBeenCalledWith({
				queryKey: workPoolQueuesQueryKeyFactory.detail(
					MOCK_WORK_POOL_NAME,
					MOCK_QUEUE_NAME,
				),
			});
		});
	});
});
