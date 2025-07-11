import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { useSet } from "./use-set";

describe("useSet", () => {
	it("add() to set", () => {
		// Setup
		const { result } = renderHook(useSet<string>);

		// Update State
		const [, util] = result.current;
		act(() => util.add("a"));

		// Get Updated State
		const [set] = result.current;

		// Asserts
		expect(set.has("a")).toEqual(true);
		expect(Array.from(set)).toEqual(["a"]);
	});

	it("remove() from set", () => {
		// Setup
		const { result } = renderHook(() => useSet(new Set(["a"])));

		// Update State
		const [, util] = result.current;
		act(() => util.remove("a"));

		// Get Updated State
		const [set] = result.current;

		// Asserts
		expect(set.has("a")).toEqual(false);
		expect(Array.from(set)).toEqual([]);
	});

	it("toggle() value from set -- value exists", () => {
		// Setup
		const { result } = renderHook(() => useSet(new Set(["a"])));

		// Update State
		const [, util] = result.current;
		act(() => util.toggle("a"));

		// Get Updated State
		const [set] = result.current;

		// Asserts
		expect(set.has("a")).toEqual(false);
		expect(Array.from(set)).toEqual([]);
	});

	it("toggle() value from set -- value does not exist", () => {
		// Setup
		const { result } = renderHook(useSet<string>);

		// Update State
		const [, util] = result.current;
		act(() => util.toggle("a"));

		// Get Updated State
		const [set] = result.current;

		// Asserts
		expect(set.has("a")).toEqual(true);
		expect(Array.from(set)).toEqual(["a"]);
	});

	it("clear() values from set ", () => {
		// Setup
		const { result } = renderHook(() => useSet(new Set(["a", "b", "c"])));

		// Update State
		const [, util] = result.current;
		act(() => util.clear());

		// Get Updated State
		const [set] = result.current;

		// Asserts
		expect(Array.from(set)).toEqual([]);
	});

	it("reset() values to set", () => {
		// Setup
		const { result } = renderHook(() => useSet(new Set(["a", "b", "c"])));

		// Update State
		const [, util] = result.current;
		act(() => util.clear());
		act(() => util.reset());

		// Get Updated State
		const [set] = result.current;

		// Asserts
		expect(Array.from(set)).toEqual(["a", "b", "c"]);
	});
});
