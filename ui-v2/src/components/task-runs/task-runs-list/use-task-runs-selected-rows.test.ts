import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { useTaskRunsSelectedRows } from "./use-task-runs-selected-rows";

describe("useTaskRunsSelectedRows", () => {
	it("addRow() to set", () => {
		const { result } = renderHook(useTaskRunsSelectedRows);

		const [, , util] = result.current;
		act(() => util.addRow("a"));

		const [set] = result.current;

		expect(set.has("a")).toEqual(true);
		expect(Array.from(set)).toEqual(["a"]);
	});

	it("removeRow() from set", () => {
		const { result } = renderHook(() => useTaskRunsSelectedRows(["a"]));

		const [, , utils] = result.current;
		act(() => utils.removeRow("a"));

		const [set] = result.current;

		expect(set.has("a")).toEqual(false);
		expect(Array.from(set)).toEqual([]);
	});

	it("clearSet() values from set", () => {
		const { result } = renderHook(() =>
			useTaskRunsSelectedRows(["a", "b", "c"]),
		);

		const [, , utils] = result.current;
		act(() => utils.clearSet());

		const [set] = result.current;

		expect(Array.from(set)).toEqual([]);
	});

	it("onSelectRow() set when checked", () => {
		const { result } = renderHook(useTaskRunsSelectedRows);

		const [, , utils] = result.current;
		act(() => utils.onSelectRow("a", true));

		const [set] = result.current;

		expect(Array.from(set)).toEqual(["a"]);
	});

	it("onSelectRow() removed when unchecked", () => {
		const { result } = renderHook(() => useTaskRunsSelectedRows(["a"]));

		const [, , utils] = result.current;
		act(() => utils.onSelectRow("a", false));

		const [set] = result.current;

		expect(Array.from(set)).toEqual([]);
	});
});
