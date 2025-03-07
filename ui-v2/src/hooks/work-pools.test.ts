import { renderHook } from "@testing-library/react";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { http, HttpResponse } from "msw";
import { toast } from "sonner";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
	useDeleteWorkPool,
	usePauseWorkPool,
	useResumeWorkPool,
} from "./work-pools";

vi.mock("sonner", () => ({
	toast: {
		success: vi.fn(),
		error: vi.fn(),
	},
}));

describe("Work Pool Hooks", () => {
	const workPoolName = "test-work-pool";

	beforeEach(() => {
		vi.clearAllMocks();
	});

	describe("usePauseWorkPool", () => {
		it("calls PATCH with correct parameters to pause a work pool", async () => {
			let requestBody: Record<string, unknown> = {};
			server.use(
				http.patch(
					buildApiUrl(`/work_pools/${workPoolName}`),
					async ({ request }) => {
						requestBody = (await request.json()) as Record<string, unknown>;
						return HttpResponse.json({});
					},
				),
			);

			const { result } = renderHook(() => usePauseWorkPool(), {
				wrapper: createWrapper(),
			});

			await result.current.mutateAsync(workPoolName);

			expect(requestBody).toEqual({ is_paused: true });
		});

		it("shows success toast on successful pause", async () => {
			server.use(
				http.patch(buildApiUrl(`/work_pools/${workPoolName}`), () => {
					return HttpResponse.json({});
				}),
			);

			const { result } = renderHook(() => usePauseWorkPool(), {
				wrapper: createWrapper(),
			});

			await result.current.mutateAsync(workPoolName);

			expect(toast.success).toHaveBeenCalledWith(`${workPoolName} paused`);
		});

		it("shows error toast when pause fails", async () => {
			const errorMessage = "API Error";
			server.use(
				http.patch(buildApiUrl(`/work_pools/${workPoolName}`), () => {
					return HttpResponse.json({ detail: errorMessage }, { status: 500 });
				}),
			);

			const { result } = renderHook(() => usePauseWorkPool(), {
				wrapper: createWrapper(),
			});

			try {
				await result.current.mutateAsync(workPoolName);
			} catch {
				// silence is golden
			}

			expect(toast.error).toHaveBeenCalled();
		});
	});

	describe("useResumeWorkPool", () => {
		it("calls PATCH with correct parameters to resume a work pool", async () => {
			let requestBody: Record<string, unknown> = {};
			server.use(
				http.patch(
					buildApiUrl(`/work_pools/${workPoolName}`),
					async ({ request }) => {
						requestBody = (await request.json()) as Record<string, unknown>;
						return HttpResponse.json({});
					},
				),
			);

			const { result } = renderHook(() => useResumeWorkPool(), {
				wrapper: createWrapper(),
			});

			await result.current.mutateAsync(workPoolName);

			expect(requestBody).toEqual({ is_paused: false });
		});

		it("shows success toast on successful resume", async () => {
			server.use(
				http.patch(buildApiUrl(`/work_pools/${workPoolName}`), () => {
					return HttpResponse.json({});
				}),
			);

			const { result } = renderHook(() => useResumeWorkPool(), {
				wrapper: createWrapper(),
			});

			await result.current.mutateAsync(workPoolName);

			expect(toast.success).toHaveBeenCalledWith(`${workPoolName} resumed`);
		});

		it("shows error toast when resume fails", async () => {
			const errorMessage = "API Error";
			server.use(
				http.patch(buildApiUrl(`/work_pools/${workPoolName}`), () => {
					return HttpResponse.json({ detail: errorMessage }, { status: 500 });
				}),
			);

			const { result } = renderHook(() => useResumeWorkPool(), {
				wrapper: createWrapper(),
			});

			// Act
			try {
				await result.current.mutateAsync(workPoolName);
			} catch {
				// silence is golden
			}

			expect(toast.error).toHaveBeenCalled();
		});
	});

	describe("useDeleteWorkPool", () => {
		it("calls DELETE to remove a work pool", async () => {
			let wasDeleted = false;
			server.use(
				http.delete(buildApiUrl(`/work_pools/${workPoolName}`), () => {
					wasDeleted = true;
					return HttpResponse.json({});
				}),
			);

			const { result } = renderHook(() => useDeleteWorkPool(), {
				wrapper: createWrapper(),
			});

			await result.current.mutateAsync(workPoolName);

			expect(wasDeleted).toBe(true);
		});

		it("shows success toast on successful delete", async () => {
			server.use(
				http.delete(buildApiUrl(`/work_pools/${workPoolName}`), () => {
					return HttpResponse.json({});
				}),
			);

			const { result } = renderHook(() => useDeleteWorkPool(), {
				wrapper: createWrapper(),
			});

			await result.current.mutateAsync(workPoolName);

			expect(toast.success).toHaveBeenCalledWith(`${workPoolName} deleted`);
		});

		it("shows error toast when delete fails", async () => {
			const errorMessage = "API Error";
			server.use(
				http.delete(buildApiUrl(`/work_pools/${workPoolName}`), () => {
					return HttpResponse.json({ detail: errorMessage }, { status: 500 });
				}),
			);

			const { result } = renderHook(() => useDeleteWorkPool(), {
				wrapper: createWrapper(),
			});

			try {
				await result.current.mutateAsync(workPoolName);
			} catch {
				// silence is golden
			}

			expect(toast.error).toHaveBeenCalled();
		});
	});
});
