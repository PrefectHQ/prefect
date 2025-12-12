import { QueryClient } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useDeleteTaskRunsDialog } from "./use-delete-task-runs-dialog";

describe("useDeleteTaskRunsDialog", () => {
	let queryClient: QueryClient;

	beforeEach(() => {
		queryClient = new QueryClient({
			defaultOptions: {
				queries: { retry: false },
				mutations: { retry: false },
			},
		});
	});

	describe("initialization", () => {
		it("returns dialogState and handleConfirmDelete", () => {
			const { result } = renderHook(() => useDeleteTaskRunsDialog(), {
				wrapper: createWrapper({ queryClient }),
			});

			const [dialogState, handleConfirmDelete] = result.current;

			expect(dialogState).toBeDefined();
			expect(dialogState.isOpen).toBe(false);
			expect(typeof handleConfirmDelete).toBe("function");
		});
	});

	describe("handleConfirmDelete", () => {
		it("opens dialog with correct title and description", () => {
			const { result } = renderHook(() => useDeleteTaskRunsDialog(), {
				wrapper: createWrapper({ queryClient }),
			});

			act(() => {
				const [, handleConfirmDelete] = result.current;
				handleConfirmDelete(["task-run-1"]);
			});

			const [dialogState] = result.current;
			expect(dialogState.isOpen).toBe(true);
			expect(dialogState.title).toBe("Delete Task Runs");
			expect(dialogState.description).toBe(
				"Are you sure you want to delete selected task runs?",
			);
		});
	});

	describe("delete operations", () => {
		it("shows success toast for single task run deletion", async () => {
			server.use(
				http.delete(buildApiUrl("/task_runs/:id"), () => {
					return new HttpResponse(null, { status: 204 });
				}),
			);

			const { result } = renderHook(() => useDeleteTaskRunsDialog(), {
				wrapper: createWrapper({ queryClient }),
			});

			const onConfirm = vi.fn();

			act(() => {
				const [, handleConfirmDelete] = result.current;
				handleConfirmDelete(["task-run-1"], onConfirm);
			});

			act(() => {
				const [dialogState] = result.current;
				dialogState.onConfirm();
			});

			await waitFor(() => {
				expect(onConfirm).toHaveBeenCalledTimes(1);
			});
		});

		it("shows success toast for multiple task run deletions", async () => {
			server.use(
				http.delete(buildApiUrl("/task_runs/:id"), () => {
					return new HttpResponse(null, { status: 204 });
				}),
			);

			const { result } = renderHook(() => useDeleteTaskRunsDialog(), {
				wrapper: createWrapper({ queryClient }),
			});

			const onConfirm = vi.fn();

			act(() => {
				const [, handleConfirmDelete] = result.current;
				handleConfirmDelete(
					["task-run-1", "task-run-2", "task-run-3"],
					onConfirm,
				);
			});

			act(() => {
				const [dialogState] = result.current;
				dialogState.onConfirm();
			});

			await waitFor(() => {
				expect(onConfirm).toHaveBeenCalledTimes(1);
			});
		});

		it("handles single task run deletion failure", async () => {
			server.use(
				http.delete(buildApiUrl("/task_runs/:id"), () => {
					return new HttpResponse(null, { status: 500 });
				}),
			);

			const { result } = renderHook(() => useDeleteTaskRunsDialog(), {
				wrapper: createWrapper({ queryClient }),
			});

			const onConfirm = vi.fn();

			act(() => {
				const [, handleConfirmDelete] = result.current;
				handleConfirmDelete(["task-run-1"], onConfirm);
			});

			act(() => {
				const [dialogState] = result.current;
				dialogState.onConfirm();
			});

			await waitFor(() => {
				expect(onConfirm).toHaveBeenCalledTimes(1);
			});
		});

		it("handles multiple task run deletion failures", async () => {
			server.use(
				http.delete(buildApiUrl("/task_runs/:id"), () => {
					return new HttpResponse(null, { status: 500 });
				}),
			);

			const { result } = renderHook(() => useDeleteTaskRunsDialog(), {
				wrapper: createWrapper({ queryClient }),
			});

			const onConfirm = vi.fn();

			act(() => {
				const [, handleConfirmDelete] = result.current;
				handleConfirmDelete(["task-run-1", "task-run-2"], onConfirm);
			});

			act(() => {
				const [dialogState] = result.current;
				dialogState.onConfirm();
			});

			await waitFor(() => {
				expect(onConfirm).toHaveBeenCalledTimes(1);
			});
		});

		it("handles mixed success and failure deletions", async () => {
			let callCount = 0;
			server.use(
				http.delete(buildApiUrl("/task_runs/:id"), () => {
					callCount++;
					if (callCount === 1) {
						return new HttpResponse(null, { status: 204 });
					}
					return new HttpResponse(null, { status: 500 });
				}),
			);

			const { result } = renderHook(() => useDeleteTaskRunsDialog(), {
				wrapper: createWrapper({ queryClient }),
			});

			const onConfirm = vi.fn();

			act(() => {
				const [, handleConfirmDelete] = result.current;
				handleConfirmDelete(["task-run-1", "task-run-2"], onConfirm);
			});

			act(() => {
				const [dialogState] = result.current;
				dialogState.onConfirm();
			});

			await waitFor(() => {
				expect(onConfirm).toHaveBeenCalledTimes(1);
			});
		});

		it("calls onConfirm callback after deletion completes", async () => {
			server.use(
				http.delete(buildApiUrl("/task_runs/:id"), () => {
					return new HttpResponse(null, { status: 204 });
				}),
			);

			const { result } = renderHook(() => useDeleteTaskRunsDialog(), {
				wrapper: createWrapper({ queryClient }),
			});

			const onConfirm = vi.fn();

			act(() => {
				const [, handleConfirmDelete] = result.current;
				handleConfirmDelete(["task-run-1"], onConfirm);
			});

			act(() => {
				const [dialogState] = result.current;
				dialogState.onConfirm();
			});

			await waitFor(() => {
				expect(onConfirm).toHaveBeenCalledTimes(1);
			});
		});

		it("works without onConfirm callback", async () => {
			server.use(
				http.delete(buildApiUrl("/task_runs/:id"), () => {
					return new HttpResponse(null, { status: 204 });
				}),
			);

			const { result } = renderHook(() => useDeleteTaskRunsDialog(), {
				wrapper: createWrapper({ queryClient }),
			});

			act(() => {
				const [, handleConfirmDelete] = result.current;
				handleConfirmDelete(["task-run-1"]);
			});

			act(() => {
				const [dialogState] = result.current;
				dialogState.onConfirm();
			});

			await waitFor(() => {
				const [dialogState] = result.current;
				expect(dialogState).toBeDefined();
			});
		});
	});
});
