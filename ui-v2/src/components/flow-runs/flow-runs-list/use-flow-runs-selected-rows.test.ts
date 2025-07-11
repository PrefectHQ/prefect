import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { useFlowRunsSelectedRows } from "./use-flow-runs-selected-rows";

describe("useFlowRunsSelectedRows", () => {
	it("addRow() to set", () => {
		// Setup
		const { result } = renderHook(useFlowRunsSelectedRows);

		// Update State
		const [, , util] = result.current;
		act(() => util.addRow("a"));

		// Get Updated State
		const [set] = result.current;

		// Asserts
		expect(set.has("a")).toEqual(true);
		expect(Array.from(set)).toEqual(["a"]);
	});

	it("removeRow() from set", () => {
		// Setup
		const { result } = renderHook(() => useFlowRunsSelectedRows(["a"]));

		// Update State
		const [, , utils] = result.current;
		act(() => utils.removeRow("a"));

		// Get Updated State
		const [set] = result.current;

		// Asserts
		expect(set.has("a")).toEqual(false);
		expect(Array.from(set)).toEqual([]);
	});

	it("clearSet() values from set ", () => {
		// Setup
		const { result } = renderHook(() =>
			useFlowRunsSelectedRows(["a", "b", "c"]),
		);

		// Update State
		const [, , utils] = result.current;
		act(() => utils.clearSet());

		// Get Updated State
		const [set] = result.current;

		// Asserts
		expect(Array.from(set)).toEqual([]);
	});

	it("onSelectRow() set  when checked", () => {
		// Setup
		const { result } = renderHook(useFlowRunsSelectedRows);

		// Update State
		const [, , utils] = result.current;
		act(() => utils.onSelectRow("a", true));

		// Get Updated State
		const [set] = result.current;

		// Asserts
		expect(Array.from(set)).toEqual(["a"]);
	});

	it("onSelectRow() removed  when unchecked", () => {
		// Setup
		const { result } = renderHook(() => useFlowRunsSelectedRows(["a"]));

		// Update State
		const [, , utils] = result.current;
		act(() => utils.onSelectRow("a", false));

		// Get Updated State
		const [set] = result.current;

		// Asserts
		expect(Array.from(set)).toEqual([]);
	});
});
