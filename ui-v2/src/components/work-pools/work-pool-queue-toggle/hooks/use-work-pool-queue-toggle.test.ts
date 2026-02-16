import { QueryClient } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
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

describe("useWorkPoolQueueToggle", () => {
	const createTestQueryClient = () => {
		return new QueryClient({
			defaultOptions: {
				queries: {
					retry: false,
				},
				mutations: {
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

	it("calls resume mutation when isResumed is true", async () => {
		const queryClient = createTestQueryClient();
		let resumeRequestMade = false;

		// Mock the API endpoint for resume (PATCH with is_paused: false)
		server.use(
			http.patch(
				buildApiUrl("/work_pools/test-pool/queues/test-queue"),
				async ({ request }) => {
					const body = await request.json();
					if (body && typeof body === "object" && "is_paused" in body) {
						expect(body.is_paused).toBe(false);
						resumeRequestMade = true;
					}
					return HttpResponse.json({});
				},
			),
		);

		const { result } = renderHook(() => useWorkPoolQueueToggle(defaultQueue), {
			wrapper: createWrapper({ queryClient }),
		});

		act(() => {
			result.current.handleToggle(true);
		});

		await waitFor(() => {
			expect(resumeRequestMade).toBe(true);
			expect(toast.success).toHaveBeenCalledWith("Queue resumed successfully");
		});
	});

	it("calls pause mutation when isResumed is false", async () => {
		const queryClient = createTestQueryClient();
		let pauseRequestMade = false;

		// Mock the API endpoint for pause (PATCH with is_paused: true)
		server.use(
			http.patch(
				buildApiUrl("/work_pools/test-pool/queues/test-queue"),
				async ({ request }) => {
					const body = await request.json();
					if (body && typeof body === "object" && "is_paused" in body) {
						expect(body.is_paused).toBe(true);
						pauseRequestMade = true;
					}
					return HttpResponse.json({});
				},
			),
		);

		const { result } = renderHook(() => useWorkPoolQueueToggle(defaultQueue), {
			wrapper: createWrapper({ queryClient }),
		});

		act(() => {
			result.current.handleToggle(false);
		});

		await waitFor(() => {
			expect(pauseRequestMade).toBe(true);
			expect(toast.success).toHaveBeenCalledWith("Queue paused successfully");
		});
	});

	it("shows success toast and calls onUpdate on resume success", async () => {
		const queryClient = createTestQueryClient();
		const onUpdate = vi.fn();

		// Mock successful API response
		server.use(
			http.patch(buildApiUrl("/work_pools/test-pool/queues/test-queue"), () => {
				return HttpResponse.json({});
			}),
		);

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

		// Mock successful API response
		server.use(
			http.patch(buildApiUrl("/work_pools/test-pool/queues/test-queue"), () => {
				return HttpResponse.json({});
			}),
		);

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

		// Mock API to return error
		server.use(
			http.patch(buildApiUrl("/work_pools/test-pool/queues/test-queue"), () => {
				return HttpResponse.json(
					{ error: "Failed to resume" },
					{ status: 500 },
				);
			}),
		);

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

		// Mock API to return error
		server.use(
			http.patch(buildApiUrl("/work_pools/test-pool/queues/test-queue"), () => {
				return HttpResponse.json({ error: "Failed to pause" }, { status: 500 });
			}),
		);

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

		// Mock successful API response
		server.use(
			http.patch(buildApiUrl("/work_pools/test-pool/queues/test-queue"), () => {
				return HttpResponse.json({});
			}),
		);

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
		let pauseRequestMade = false;

		// Mock the API endpoint for the custom pool/queue
		server.use(
			http.patch(
				buildApiUrl("/work_pools/custom-pool/queues/custom-queue"),
				async ({ request }) => {
					const body = await request.json();
					if (body && typeof body === "object" && "is_paused" in body) {
						expect(body.is_paused).toBe(true);
						pauseRequestMade = true;
					}
					return HttpResponse.json({});
				},
			),
		);

		const { result } = renderHook(() => useWorkPoolQueueToggle(customQueue), {
			wrapper: createWrapper({ queryClient }),
		});

		act(() => {
			result.current.handleToggle(false);
		});

		await waitFor(() => {
			expect(pauseRequestMade).toBe(true);
		});
	});
});
