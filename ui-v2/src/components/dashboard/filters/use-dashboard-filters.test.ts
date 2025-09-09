import { renderHook } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";
import type { DateRangeSelectValue } from "./types";
import { useDashboardFilters } from "./use-dashboard-filters";

// Mock TanStack Router
const mockNavigate = vi.fn();
const mockSearch = {};

vi.mock("@tanstack/router", () => ({
	useNavigate: () => mockNavigate,
	useSearch: vi.fn(() => mockSearch),
}));

describe("useDashboardFilters", () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	test("returns default filter values when no search params", () => {
		const { result } = renderHook(() => useDashboardFilters());

		expect(result.current.filter).toEqual({
			range: { type: "span", seconds: -86400 }, // Last 24 hours
			tags: [],
			hideSubflows: undefined,
		});
	});

	test("parses date range from URL search params", () => {
		// Mock search params with a span range
		vi.mocked(require("@tanstack/router").useSearch).mockReturnValue({
			range: "span:-3600", // Last hour
		});

		const { result } = renderHook(() => useDashboardFilters());

		expect(result.current.filter.range).toEqual({
			type: "span",
			seconds: -3600,
		});
	});

	test("parses tags from URL search params", () => {
		vi.mocked(require("@tanstack/router").useSearch).mockReturnValue({
			tags: ["production", "critical"],
		});

		const { result } = renderHook(() => useDashboardFilters());

		expect(result.current.filter.tags).toEqual(["production", "critical"]);
	});

	test("parses hideSubflows from URL search params", () => {
		vi.mocked(require("@tanstack/router").useSearch).mockReturnValue({
			hideSubflows: true,
		});

		const { result } = renderHook(() => useDashboardFilters());

		expect(result.current.filter.hideSubflows).toBe(true);
	});

	test("updateDateRange calls navigate with serialized range", () => {
		const { result } = renderHook(() => useDashboardFilters());

		const newRange: DateRangeSelectValue = { type: "span", seconds: -604800 };
		result.current.updateDateRange(newRange);

		expect(mockNavigate).toHaveBeenCalledWith({
			search: expect.any(Function),
			replace: true,
		});

		// Test the search function
		const searchFn = mockNavigate.mock.calls[0][0].search;
		const newSearch = searchFn({ existingParam: "value" });
		expect(newSearch).toEqual({
			existingParam: "value",
			range: "span:-604800",
		});
	});

	test("updateTags calls navigate with tags array", () => {
		const { result } = renderHook(() => useDashboardFilters());

		result.current.updateTags(["tag1", "tag2"]);

		expect(mockNavigate).toHaveBeenCalledWith({
			search: expect.any(Function),
			replace: true,
		});

		const searchFn = mockNavigate.mock.calls[0][0].search;
		const newSearch = searchFn({});
		expect(newSearch).toEqual({
			tags: ["tag1", "tag2"],
		});
	});

	test("updateTags removes tags param when empty array", () => {
		const { result } = renderHook(() => useDashboardFilters());

		result.current.updateTags([]);

		const searchFn = mockNavigate.mock.calls[0][0].search;
		const newSearch = searchFn({ tags: ["existing"] });
		expect(newSearch).toEqual({
			tags: undefined,
		});
	});

	test("updateHideSubflows calls navigate with boolean value", () => {
		const { result } = renderHook(() => useDashboardFilters());

		result.current.updateHideSubflows(true);

		expect(mockNavigate).toHaveBeenCalledWith({
			search: expect.any(Function),
			replace: true,
		});

		const searchFn = mockNavigate.mock.calls[0][0].search;
		const newSearch = searchFn({});
		expect(newSearch).toEqual({
			hideSubflows: true,
		});
	});

	test("updateHideSubflows removes param when false", () => {
		const { result } = renderHook(() => useDashboardFilters());

		result.current.updateHideSubflows(false);

		const searchFn = mockNavigate.mock.calls[0][0].search;
		const newSearch = searchFn({ hideSubflows: true });
		expect(newSearch).toEqual({
			hideSubflows: undefined,
		});
	});

	test("resetFilters clears all search params", () => {
		const { result } = renderHook(() => useDashboardFilters());

		result.current.resetFilters();

		expect(mockNavigate).toHaveBeenCalledWith({
			search: {},
			replace: true,
		});
	});

	test("getFlowRunsFilter transforms span range correctly", () => {
		vi.mocked(require("@tanstack/router").useSearch).mockReturnValue({
			range: "span:-3600",
			tags: ["production"],
			hideSubflows: true,
		});

		const { result } = renderHook(() => useDashboardFilters());
		const filter = result.current.getFlowRunsFilter();

		expect(filter.flowRuns).toMatchObject({
			expectedStartTimeAfter: expect.any(String),
			expectedStartTimeBefore: expect.any(String),
			tags: { operator: "and_", all_: ["production"] },
			parentTaskRunIdNull: true,
		});
	});

	test("getFlowRunsFilter transforms range correctly", () => {
		const startTime = new Date("2024-01-01T00:00:00Z").getTime();
		const endTime = new Date("2024-01-02T00:00:00Z").getTime();

		vi.mocked(require("@tanstack/router").useSearch).mockReturnValue({
			range: `range:${startTime}:${endTime}`,
		});

		const { result } = renderHook(() => useDashboardFilters());
		const filter = result.current.getFlowRunsFilter();

		expect(filter.flowRuns).toMatchObject({
			expectedStartTimeAfter: "2024-01-01T00:00:00.000Z",
			expectedStartTimeBefore: "2024-01-02T00:00:00.000Z",
		});
	});

	test("getFlowRunsFilter transforms period correctly", () => {
		vi.mocked(require("@tanstack/router").useSearch).mockReturnValue({
			range: "period:Today",
		});

		const { result } = renderHook(() => useDashboardFilters());
		const filter = result.current.getFlowRunsFilter();

		expect(filter.flowRuns).toMatchObject({
			expectedStartTimeAfter: expect.any(String),
			expectedStartTimeBefore: expect.any(String),
		});
	});

	test("getFlowRunsFilter transforms around correctly", () => {
		const centerTime = new Date("2024-01-15T12:00:00Z").getTime();

		vi.mocked(require("@tanstack/router").useSearch).mockReturnValue({
			range: `around:${centerTime}:2:hour`,
		});

		const { result } = renderHook(() => useDashboardFilters());
		const filter = result.current.getFlowRunsFilter();

		expect(filter.flowRuns).toMatchObject({
			expectedStartTimeAfter: expect.any(String),
			expectedStartTimeBefore: expect.any(String),
		});
	});

	test("serializes and deserializes range values correctly", () => {
		// Test span
		vi.mocked(require("@tanstack/router").useSearch).mockReturnValue({
			range: "span:-86400",
		});

		let { result } = renderHook(() => useDashboardFilters());
		expect(result.current.filter.range).toEqual({
			type: "span",
			seconds: -86400,
		});

		// Test range
		const startTime = Date.now();
		const endTime = startTime + 86400000; // 1 day later
		vi.mocked(require("@tanstack/router").useSearch).mockReturnValue({
			range: `range:${startTime}:${endTime}`,
		});

		({ result } = renderHook(() => useDashboardFilters()));
		expect(result.current.filter.range).toEqual({
			type: "range",
			startDate: new Date(startTime),
			endDate: new Date(endTime),
		});

		// Test period
		vi.mocked(require("@tanstack/router").useSearch).mockReturnValue({
			range: "period:Today",
		});

		({ result } = renderHook(() => useDashboardFilters()));
		expect(result.current.filter.range).toEqual({
			type: "period",
			period: "Today",
		});

		// Test around
		const centerTime = Date.now();
		vi.mocked(require("@tanstack/router").useSearch).mockReturnValue({
			range: `around:${centerTime}:3:day`,
		});

		({ result } = renderHook(() => useDashboardFilters()));
		expect(result.current.filter.range).toEqual({
			type: "around",
			date: new Date(centerTime),
			quantity: 3,
			unit: "day",
		});
	});

	test("handles invalid range format gracefully", () => {
		vi.mocked(require("@tanstack/router").useSearch).mockReturnValue({
			range: "invalid:format",
		});

		const { result } = renderHook(() => useDashboardFilters());
		expect(result.current.filter.range).toEqual({
			type: "span",
			seconds: -86400, // Falls back to default
		});
	});

	test("excludes optional filter properties when not set", () => {
		vi.mocked(require("@tanstack/router").useSearch).mockReturnValue({
			range: "span:-86400",
			// No tags or hideSubflows
		});

		const { result } = renderHook(() => useDashboardFilters());
		const filter = result.current.getFlowRunsFilter();

		expect(filter.flowRuns).toEqual({
			expectedStartTimeAfter: expect.any(String),
			expectedStartTimeBefore: expect.any(String),
		});

		expect(filter.flowRuns).not.toHaveProperty("tags");
		expect(filter.flowRuns).not.toHaveProperty("parentTaskRunIdNull");
	});
});
