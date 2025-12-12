import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { useTaskRunsSelectedRows } from "./use-task-runs-selected-rows";

describe("useTaskRunsSelectedRows", () => {
	describe("initialization", () => {
		it("initializes with an empty set by default", () => {
			const { result } = renderHook(() => useTaskRunsSelectedRows());
			const [selectedRows] = result.current;

			expect(selectedRows.size).toBe(0);
		});

		it("initializes with provided default values", () => {
			const { result } = renderHook(() =>
				useTaskRunsSelectedRows(["task-1", "task-2"]),
			);
			const [selectedRows] = result.current;

			expect(selectedRows.size).toBe(2);
			expect(selectedRows.has("task-1")).toBe(true);
			expect(selectedRows.has("task-2")).toBe(true);
		});
	});

	describe("addRow", () => {
		it("adds a row to the selected set", () => {
			const { result } = renderHook(() => useTaskRunsSelectedRows());

			act(() => {
				result.current[2].addRow("task-1");
			});

			const [selectedRows] = result.current;
			expect(selectedRows.has("task-1")).toBe(true);
		});

		it("does not duplicate rows when adding an existing row", () => {
			const { result } = renderHook(() => useTaskRunsSelectedRows(["task-1"]));

			act(() => {
				result.current[2].addRow("task-1");
			});

			const [selectedRows] = result.current;
			expect(selectedRows.size).toBe(1);
		});
	});

	describe("removeRow", () => {
		it("removes a row from the selected set", () => {
			const { result } = renderHook(() =>
				useTaskRunsSelectedRows(["task-1", "task-2"]),
			);

			act(() => {
				result.current[2].removeRow("task-1");
			});

			const [selectedRows] = result.current;
			expect(selectedRows.has("task-1")).toBe(false);
			expect(selectedRows.has("task-2")).toBe(true);
		});

		it("does nothing when removing a non-existent row", () => {
			const { result } = renderHook(() => useTaskRunsSelectedRows(["task-1"]));

			act(() => {
				result.current[2].removeRow("task-2");
			});

			const [selectedRows] = result.current;
			expect(selectedRows.size).toBe(1);
			expect(selectedRows.has("task-1")).toBe(true);
		});
	});

	describe("onSelectRow", () => {
		it("adds a row when checked is true", () => {
			const { result } = renderHook(() => useTaskRunsSelectedRows());

			act(() => {
				result.current[2].onSelectRow("task-1", true);
			});

			const [selectedRows] = result.current;
			expect(selectedRows.has("task-1")).toBe(true);
		});

		it("removes a row when checked is false", () => {
			const { result } = renderHook(() => useTaskRunsSelectedRows(["task-1"]));

			act(() => {
				result.current[2].onSelectRow("task-1", false);
			});

			const [selectedRows] = result.current;
			expect(selectedRows.has("task-1")).toBe(false);
		});
	});

	describe("clearSet", () => {
		it("clears all selected rows", () => {
			const { result } = renderHook(() =>
				useTaskRunsSelectedRows(["task-1", "task-2", "task-3"]),
			);

			act(() => {
				result.current[2].clearSet();
			});

			const [selectedRows] = result.current;
			expect(selectedRows.size).toBe(0);
		});
	});

	describe("setSelectedRows", () => {
		it("allows direct setting of selected rows", () => {
			const { result } = renderHook(() => useTaskRunsSelectedRows());

			act(() => {
				result.current[1](new Set(["task-1", "task-2"]));
			});

			const [selectedRows] = result.current;
			expect(selectedRows.size).toBe(2);
			expect(selectedRows.has("task-1")).toBe(true);
			expect(selectedRows.has("task-2")).toBe(true);
		});
	});
});
