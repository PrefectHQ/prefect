import { renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { useChartInterval } from "./use-chart-interval";

describe("useChartInterval", () => {
	it("returns an interval and unit", () => {
		const startDate = new Date("2024-01-01T00:00:00");
		const endDate = new Date("2024-01-02T00:00:00");
		const containerWidth = 600;

		const { result } = renderHook(() =>
			useChartInterval(startDate, endDate, containerWidth),
		);

		expect(result.current).toHaveProperty("interval");
		expect(result.current).toHaveProperty("unit");
		expect(typeof result.current.interval).toBe("number");
		expect(["second", "minute", "hour", "day", "week"]).toContain(
			result.current.unit,
		);
	});

	it("returns smaller intervals for narrow containers", () => {
		const startDate = new Date("2024-01-01T00:00:00");
		const endDate = new Date("2024-01-02T00:00:00");

		const { result: narrowResult } = renderHook(() =>
			useChartInterval(startDate, endDate, 100),
		);

		const { result: wideResult } = renderHook(() =>
			useChartInterval(startDate, endDate, 1000),
		);

		expect(narrowResult.current.interval).toBeGreaterThanOrEqual(
			wideResult.current.interval,
		);
	});

	it("returns larger intervals for longer time ranges", () => {
		const startDate = new Date("2024-01-01T00:00:00");
		const shortEndDate = new Date("2024-01-01T01:00:00"); // 1 hour
		const longEndDate = new Date("2024-01-08T00:00:00"); // 1 week

		const containerWidth = 600;

		const { result: shortResult } = renderHook(() =>
			useChartInterval(startDate, shortEndDate, containerWidth),
		);

		const { result: longResult } = renderHook(() =>
			useChartInterval(startDate, longEndDate, containerWidth),
		);

		expect(longResult.current.interval).toBeGreaterThan(
			shortResult.current.interval,
		);
	});

	it("returns 'second' unit for sub-minute intervals", () => {
		const startDate = new Date("2024-01-01T00:00:00");
		const endDate = new Date("2024-01-01T00:01:00"); // 1 minute range
		const containerWidth = 600;

		const { result } = renderHook(() =>
			useChartInterval(startDate, endDate, containerWidth),
		);

		expect(result.current.unit).toBe("second");
		expect(result.current.interval).toBeLessThan(60);
	});

	it("returns 'minute' unit for minute-scale intervals", () => {
		const startDate = new Date("2024-01-01T00:00:00");
		const endDate = new Date("2024-01-01T01:00:00"); // 1 hour range
		const containerWidth = 300;

		const { result } = renderHook(() =>
			useChartInterval(startDate, endDate, containerWidth),
		);

		expect(result.current.unit).toBe("minute");
		expect(result.current.interval).toBeGreaterThanOrEqual(60);
		expect(result.current.interval).toBeLessThan(3600);
	});

	it("returns 'hour' unit for hour-scale intervals", () => {
		const startDate = new Date("2024-01-01T00:00:00");
		const endDate = new Date("2024-01-02T00:00:00"); // 1 day range
		const containerWidth = 300;

		const { result } = renderHook(() =>
			useChartInterval(startDate, endDate, containerWidth),
		);

		expect(result.current.unit).toBe("hour");
		expect(result.current.interval).toBeGreaterThanOrEqual(3600);
		expect(result.current.interval).toBeLessThan(86400);
	});

	it("returns 'day' unit for day-scale intervals", () => {
		const startDate = new Date("2024-01-01T00:00:00");
		const endDate = new Date("2024-02-01T00:00:00"); // 1 month range
		const containerWidth = 300;

		const { result } = renderHook(() =>
			useChartInterval(startDate, endDate, containerWidth),
		);

		expect(result.current.unit).toBe("day");
		expect(result.current.interval).toBeGreaterThanOrEqual(86400);
		expect(result.current.interval).toBeLessThan(604800);
	});

	it("returns 'week' unit for week-scale intervals", () => {
		const startDate = new Date("2024-01-01T00:00:00");
		const endDate = new Date("2024-06-01T00:00:00"); // ~5 months range
		const containerWidth = 300;

		const { result } = renderHook(() =>
			useChartInterval(startDate, endDate, containerWidth),
		);

		expect(result.current.unit).toBe("week");
		expect(result.current.interval).toBeGreaterThanOrEqual(604800);
	});

	it("memoizes the result based on inputs", () => {
		const startDate = new Date("2024-01-01T00:00:00");
		const endDate = new Date("2024-01-02T00:00:00");
		const containerWidth = 600;

		const { result, rerender } = renderHook(
			({ start, end, width }) => useChartInterval(start, end, width),
			{
				initialProps: {
					start: startDate,
					end: endDate,
					width: containerWidth,
				},
			},
		);

		const firstResult = result.current;

		// Rerender with same props
		rerender({ start: startDate, end: endDate, width: containerWidth });

		expect(result.current).toBe(firstResult);
	});

	it("updates when inputs change", () => {
		const startDate = new Date("2024-01-01T00:00:00");
		const endDate = new Date("2024-01-02T00:00:00");
		const newEndDate = new Date("2024-01-08T00:00:00");
		const containerWidth = 600;

		const { result, rerender } = renderHook(
			({ start, end, width }) => useChartInterval(start, end, width),
			{
				initialProps: {
					start: startDate,
					end: endDate,
					width: containerWidth,
				},
			},
		);

		const firstResult = result.current;

		// Rerender with different end date
		rerender({ start: startDate, end: newEndDate, width: containerWidth });

		expect(result.current).not.toBe(firstResult);
		expect(result.current.interval).toBeGreaterThan(firstResult.interval);
	});

	it("handles minimum container width", () => {
		const startDate = new Date("2024-01-01T00:00:00");
		const endDate = new Date("2024-01-02T00:00:00");
		const containerWidth = 1; // Very small width

		const { result } = renderHook(() =>
			useChartInterval(startDate, endDate, containerWidth),
		);

		expect(result.current.interval).toBeGreaterThan(0);
		expect(result.current.unit).toBeDefined();
	});

	it("handles zero container width", () => {
		const startDate = new Date("2024-01-01T00:00:00");
		const endDate = new Date("2024-01-02T00:00:00");
		const containerWidth = 0;

		const { result } = renderHook(() =>
			useChartInterval(startDate, endDate, containerWidth),
		);

		expect(result.current.interval).toBeGreaterThan(0);
		expect(result.current.unit).toBeDefined();
	});
});
