import { QueryClient } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { createWrapper } from "@tests/utils";
import { toast } from "sonner";
import { describe, expect, it, vi } from "vitest";
import { createFakeWorkPoolQueue } from "@/mocks";
import { useWorkPoolQueueToggle } from "./use-work-pool-queue-toggle";

// Mock dependencies
vi.mock("sonner", () => ({
	toast: {
		success: vi.fn(),
		error: vi.fn(),
	},
}));

// Mock the API mutations
vi.mock("@/api/work-pool-queues", () => ({
	usePauseWorkPoolQueueMutation: vi.fn(() => ({
		mutate: vi.fn(),
		isPending: false,
	})),
	useResumeWorkPoolQueueMutation: vi.fn(() => ({
		mutate: vi.fn(),
		isPending: false,
	})),
}));

describe("useWorkPoolQueueToggle", () => {
	const createTestQueryClient = () => {
		return new QueryClient({
			defaultOptions: {
				queries: {
					retry: false,
				},
			},
		});
	};

	const defaultQueue = createFakeWorkPoolQueue({
		name: "test-queue",
		work_pool_name: "test-pool",
	});

	it("returns toggle handler and loading state", () => {
		const queryClient = createTestQueryClient();
		const { result } = renderHook(() => useWorkPoolQueueToggle(defaultQueue), {
			wrapper: createWrapper({ queryClient }),
		});

		expect(result.current.handleToggle).toBeInstanceOf(Function);
		expect(result.current.isLoading).toBe(false);
	});

	it("shows loading state when pause mutation is pending", async () => {
		const queryClient = createTestQueryClient();
		const workPoolQueuesModule = await import("@/api/work-pool-queues");
		vi.mocked(
			workPoolQueuesModule.usePauseWorkPoolQueueMutation,
		).mockReturnValue({
			mutate: vi.fn(),
			isPending: true,
		} as
			| ReturnType<
					typeof import("@/api/work-pool-queues").usePauseWorkPoolQueueMutation
			  >
			| ReturnType<
					typeof import("@/api/work-pool-queues").useResumeWorkPoolQueueMutation
			  >);

		const { result } = renderHook(() => useWorkPoolQueueToggle(defaultQueue), {
			wrapper: createWrapper({ queryClient }),
		});

		expect(result.current.isLoading).toBe(true);
	});

	it("shows loading state when resume mutation is pending", async () => {
		const queryClient = createTestQueryClient();
		const workPoolQueuesModule = await import("@/api/work-pool-queues");
		vi.mocked(
			workPoolQueuesModule.useResumeWorkPoolQueueMutation,
		).mockReturnValue({
			mutate: vi.fn(),
			isPending: true,
		} as
			| ReturnType<
					typeof import("@/api/work-pool-queues").usePauseWorkPoolQueueMutation
			  >
			| ReturnType<
					typeof import("@/api/work-pool-queues").useResumeWorkPoolQueueMutation
			  >);

		const { result } = renderHook(() => useWorkPoolQueueToggle(defaultQueue), {
			wrapper: createWrapper({ queryClient }),
		});

		expect(result.current.isLoading).toBe(true);
	});

	it("calls resume mutation when isResumed is true", async () => {
		const queryClient = createTestQueryClient();
		const mockResumeMutate = vi.fn(
			(
				_params: unknown,
				callbacks: { onSuccess: () => void; onError: () => void },
			) => {
				callbacks.onSuccess();
			},
		);
		const mockPauseMutate = vi.fn();

		const workPoolQueuesModule = await import("@/api/work-pool-queues");
		vi.mocked(
			workPoolQueuesModule.useResumeWorkPoolQueueMutation,
		).mockReturnValue({
			mutate: mockResumeMutate,
			isPending: false,
		} as
			| ReturnType<
					typeof import("@/api/work-pool-queues").usePauseWorkPoolQueueMutation
			  >
			| ReturnType<
					typeof import("@/api/work-pool-queues").useResumeWorkPoolQueueMutation
			  >);
		vi.mocked(
			workPoolQueuesModule.usePauseWorkPoolQueueMutation,
		).mockReturnValue({
			mutate: mockPauseMutate,
			isPending: false,
		} as
			| ReturnType<
					typeof import("@/api/work-pool-queues").usePauseWorkPoolQueueMutation
			  >
			| ReturnType<
					typeof import("@/api/work-pool-queues").useResumeWorkPoolQueueMutation
			  >);

		const { result } = renderHook(() => useWorkPoolQueueToggle(defaultQueue), {
			wrapper: createWrapper({ queryClient }),
		});

		act(() => {
			result.current.handleToggle(true);
		});

		expect(mockResumeMutate).toHaveBeenCalledWith(
			{
				workPoolName: "test-pool",
				queueName: "test-queue",
			},
			{
				onSuccess: expect.any(Function) as () => void,
				onError: expect.any(Function) as () => void,
			},
		);
		expect(mockPauseMutate).not.toHaveBeenCalled();
	});

	it("calls pause mutation when isResumed is false", async () => {
		const queryClient = createTestQueryClient();
		const mockResumeMutate = vi.fn();
		const mockPauseMutate = vi.fn(
			(
				_params: unknown,
				callbacks: { onSuccess: () => void; onError: () => void },
			) => {
				callbacks.onSuccess();
			},
		);

		const workPoolQueuesModule = await import("@/api/work-pool-queues");
		vi.mocked(
			workPoolQueuesModule.useResumeWorkPoolQueueMutation,
		).mockReturnValue({
			mutate: mockResumeMutate,
			isPending: false,
		} as
			| ReturnType<
					typeof import("@/api/work-pool-queues").usePauseWorkPoolQueueMutation
			  >
			| ReturnType<
					typeof import("@/api/work-pool-queues").useResumeWorkPoolQueueMutation
			  >);
		vi.mocked(
			workPoolQueuesModule.usePauseWorkPoolQueueMutation,
		).mockReturnValue({
			mutate: mockPauseMutate,
			isPending: false,
		} as
			| ReturnType<
					typeof import("@/api/work-pool-queues").usePauseWorkPoolQueueMutation
			  >
			| ReturnType<
					typeof import("@/api/work-pool-queues").useResumeWorkPoolQueueMutation
			  >);

		const { result } = renderHook(() => useWorkPoolQueueToggle(defaultQueue), {
			wrapper: createWrapper({ queryClient }),
		});

		act(() => {
			result.current.handleToggle(false);
		});

		expect(mockPauseMutate).toHaveBeenCalledWith(
			{
				workPoolName: "test-pool",
				queueName: "test-queue",
			},
			{
				onSuccess: expect.any(Function) as () => void,
				onError: expect.any(Function) as () => void,
			},
		);
		expect(mockResumeMutate).not.toHaveBeenCalled();
	});

	it("shows success toast and calls onUpdate on resume success", async () => {
		const queryClient = createTestQueryClient();
		const onUpdate = vi.fn();
		const mockResumeMutate = vi.fn(
			(
				_params: unknown,
				callbacks: { onSuccess: () => void; onError: () => void },
			) => {
				callbacks.onSuccess();
			},
		);

		const workPoolQueuesModule = await import("@/api/work-pool-queues");
		vi.mocked(
			workPoolQueuesModule.useResumeWorkPoolQueueMutation,
		).mockReturnValue({
			mutate: mockResumeMutate,
			isPending: false,
		} as
			| ReturnType<
					typeof import("@/api/work-pool-queues").usePauseWorkPoolQueueMutation
			  >
			| ReturnType<
					typeof import("@/api/work-pool-queues").useResumeWorkPoolQueueMutation
			  >);

		const { result } = renderHook(
			() => useWorkPoolQueueToggle(defaultQueue, onUpdate),
			{
				wrapper: createWrapper({ queryClient }),
			},
		);

		act(() => {
			result.current.handleToggle(true);
		});

		await waitFor(() => {
			expect(toast.success).toHaveBeenCalledWith("Queue resumed successfully");
			expect(onUpdate).toHaveBeenCalled();
		});
	});

	it("shows success toast and calls onUpdate on pause success", async () => {
		const queryClient = createTestQueryClient();
		const onUpdate = vi.fn();
		const mockPauseMutate = vi.fn(
			(
				_params: unknown,
				callbacks: { onSuccess: () => void; onError: () => void },
			) => {
				callbacks.onSuccess();
			},
		);

		const workPoolQueuesModule = await import("@/api/work-pool-queues");
		vi.mocked(
			workPoolQueuesModule.usePauseWorkPoolQueueMutation,
		).mockReturnValue({
			mutate: mockPauseMutate,
			isPending: false,
		} as
			| ReturnType<
					typeof import("@/api/work-pool-queues").usePauseWorkPoolQueueMutation
			  >
			| ReturnType<
					typeof import("@/api/work-pool-queues").useResumeWorkPoolQueueMutation
			  >);

		const { result } = renderHook(
			() => useWorkPoolQueueToggle(defaultQueue, onUpdate),
			{
				wrapper: createWrapper({ queryClient }),
			},
		);

		act(() => {
			result.current.handleToggle(false);
		});

		await waitFor(() => {
			expect(toast.success).toHaveBeenCalledWith("Queue paused successfully");
			expect(onUpdate).toHaveBeenCalled();
		});
	});

	it("shows error toast on resume failure", async () => {
		const queryClient = createTestQueryClient();
		const mockResumeMutate = vi.fn(
			(
				_params: unknown,
				callbacks: { onSuccess: () => void; onError: () => void },
			) => {
				callbacks.onError();
			},
		);

		const workPoolQueuesModule = await import("@/api/work-pool-queues");
		vi.mocked(
			workPoolQueuesModule.useResumeWorkPoolQueueMutation,
		).mockReturnValue({
			mutate: mockResumeMutate,
			isPending: false,
		} as
			| ReturnType<
					typeof import("@/api/work-pool-queues").usePauseWorkPoolQueueMutation
			  >
			| ReturnType<
					typeof import("@/api/work-pool-queues").useResumeWorkPoolQueueMutation
			  >);

		const { result } = renderHook(() => useWorkPoolQueueToggle(defaultQueue), {
			wrapper: createWrapper({ queryClient }),
		});

		act(() => {
			result.current.handleToggle(true);
		});

		await waitFor(() => {
			expect(toast.error).toHaveBeenCalledWith("Failed to resume queue");
		});
	});

	it("shows error toast on pause failure", async () => {
		const queryClient = createTestQueryClient();
		const mockPauseMutate = vi.fn(
			(
				_params: unknown,
				callbacks: { onSuccess: () => void; onError: () => void },
			) => {
				callbacks.onError();
			},
		);

		const workPoolQueuesModule = await import("@/api/work-pool-queues");
		vi.mocked(
			workPoolQueuesModule.usePauseWorkPoolQueueMutation,
		).mockReturnValue({
			mutate: mockPauseMutate,
			isPending: false,
		} as
			| ReturnType<
					typeof import("@/api/work-pool-queues").usePauseWorkPoolQueueMutation
			  >
			| ReturnType<
					typeof import("@/api/work-pool-queues").useResumeWorkPoolQueueMutation
			  >);

		const { result } = renderHook(() => useWorkPoolQueueToggle(defaultQueue), {
			wrapper: createWrapper({ queryClient }),
		});

		act(() => {
			result.current.handleToggle(false);
		});

		await waitFor(() => {
			expect(toast.error).toHaveBeenCalledWith("Failed to pause queue");
		});
	});

	it("works without onUpdate callback", async () => {
		const queryClient = createTestQueryClient();
		const mockResumeMutate = vi.fn(
			(
				_params: unknown,
				callbacks: { onSuccess: () => void; onError: () => void },
			) => {
				callbacks.onSuccess();
			},
		);

		const workPoolQueuesModule = await import("@/api/work-pool-queues");
		vi.mocked(
			workPoolQueuesModule.useResumeWorkPoolQueueMutation,
		).mockReturnValue({
			mutate: mockResumeMutate,
			isPending: false,
		} as
			| ReturnType<
					typeof import("@/api/work-pool-queues").usePauseWorkPoolQueueMutation
			  >
			| ReturnType<
					typeof import("@/api/work-pool-queues").useResumeWorkPoolQueueMutation
			  >);

		const { result } = renderHook(
			() => useWorkPoolQueueToggle(defaultQueue), // No onUpdate callback
			{
				wrapper: createWrapper({ queryClient }),
			},
		);

		act(() => {
			result.current.handleToggle(true);
		});

		await waitFor(() => {
			expect(toast.success).toHaveBeenCalledWith("Queue resumed successfully");
		});
		// Should not throw error even though onUpdate is undefined
	});

	it("handles different queue names and work pool names", async () => {
		const queryClient = createTestQueryClient();
		const customQueue = createFakeWorkPoolQueue({
			name: "custom-queue",
			work_pool_name: "custom-pool",
		});
		const mockPauseMutate = vi.fn(
			(
				_params: unknown,
				callbacks: { onSuccess: () => void; onError: () => void },
			) => {
				callbacks.onSuccess();
			},
		);

		const workPoolQueuesModule = await import("@/api/work-pool-queues");
		vi.mocked(
			workPoolQueuesModule.usePauseWorkPoolQueueMutation,
		).mockReturnValue({
			mutate: mockPauseMutate,
			isPending: false,
		} as
			| ReturnType<
					typeof import("@/api/work-pool-queues").usePauseWorkPoolQueueMutation
			  >
			| ReturnType<
					typeof import("@/api/work-pool-queues").useResumeWorkPoolQueueMutation
			  >);

		const { result } = renderHook(() => useWorkPoolQueueToggle(customQueue), {
			wrapper: createWrapper({ queryClient }),
		});

		act(() => {
			result.current.handleToggle(false);
		});

		expect(mockPauseMutate).toHaveBeenCalledWith(
			{
				workPoolName: "custom-pool",
				queueName: "custom-queue",
			},
			{
				onSuccess: expect.any(Function) as () => void,
				onError: expect.any(Function) as () => void,
			},
		);
	});
});
