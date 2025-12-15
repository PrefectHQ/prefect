import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { useChartZoom } from "./use-chart-zoom";

describe("useChartZoom", () => {
	const createMockWheelEvent = (
		deltaY: number,
		clientX: number,
	): React.WheelEvent => {
		return {
			deltaY,
			clientX,
			preventDefault: vi.fn(),
		} as unknown as React.WheelEvent;
	};

	const mockGetBoundingClientRect = () => ({
		left: 0,
		right: 500,
		width: 500,
		top: 0,
		bottom: 300,
		height: 300,
		x: 0,
		y: 0,
		toJSON: () => ({}),
	});

	it("returns containerRef and handleWheel", () => {
		const startDate = new Date("2024-01-01T00:00:00");
		const endDate = new Date("2024-01-02T00:00:00");
		const onZoomChange = vi.fn();

		const { result } = renderHook(() =>
			useChartZoom({ startDate, endDate, onZoomChange }),
		);

		expect(result.current).toHaveProperty("containerRef");
		expect(result.current).toHaveProperty("handleWheel");
		expect(typeof result.current.handleWheel).toBe("function");
	});

	it("calls onZoomChange when wheel event is triggered with container ref set", () => {
		const startDate = new Date("2024-01-01T00:00:00");
		const endDate = new Date("2024-01-02T00:00:00");
		const onZoomChange = vi.fn();

		const { result } = renderHook(() =>
			useChartZoom({ startDate, endDate, onZoomChange }),
		);

		// Set up the container ref with a mock element
		const mockElement = document.createElement("div");
		mockElement.getBoundingClientRect = mockGetBoundingClientRect;
		Object.defineProperty(result.current.containerRef, "current", {
			value: mockElement,
			writable: true,
		});

		const preventDefaultMock = vi.fn();
		const wheelEvent = {
			deltaY: 100,
			clientX: 250,
			preventDefault: preventDefaultMock,
		} as unknown as React.WheelEvent;

		act(() => {
			result.current.handleWheel(wheelEvent);
		});

		expect(preventDefaultMock).toHaveBeenCalled();
		expect(onZoomChange).toHaveBeenCalled();
	});

	it("zooms out when scrolling down (positive deltaY)", () => {
		const startDate = new Date("2024-01-01T00:00:00");
		const endDate = new Date("2024-01-01T12:00:00"); // 12 hour range
		const onZoomChange = vi.fn();

		const { result } = renderHook(() =>
			useChartZoom({ startDate, endDate, onZoomChange }),
		);

		const mockElement = document.createElement("div");
		mockElement.getBoundingClientRect = mockGetBoundingClientRect;
		Object.defineProperty(result.current.containerRef, "current", {
			value: mockElement,
			writable: true,
		});

		const wheelEvent = createMockWheelEvent(100, 250); // Scroll down

		act(() => {
			result.current.handleWheel(wheelEvent);
		});

		expect(onZoomChange).toHaveBeenCalled();
		const [newStart, newEnd] = onZoomChange.mock.calls[0] as [Date, Date];
		const newRange = newEnd.getTime() - newStart.getTime();
		const originalRange = endDate.getTime() - startDate.getTime();

		// Zooming out should increase the range
		expect(newRange).toBeGreaterThan(originalRange);
	});

	it("zooms in when scrolling up (negative deltaY)", () => {
		const startDate = new Date("2024-01-01T00:00:00");
		const endDate = new Date("2024-01-01T12:00:00"); // 12 hour range
		const onZoomChange = vi.fn();

		const { result } = renderHook(() =>
			useChartZoom({ startDate, endDate, onZoomChange }),
		);

		const mockElement = document.createElement("div");
		mockElement.getBoundingClientRect = mockGetBoundingClientRect;
		Object.defineProperty(result.current.containerRef, "current", {
			value: mockElement,
			writable: true,
		});

		const wheelEvent = createMockWheelEvent(-100, 250); // Scroll up

		act(() => {
			result.current.handleWheel(wheelEvent);
		});

		expect(onZoomChange).toHaveBeenCalled();
		const [newStart, newEnd] = onZoomChange.mock.calls[0] as [Date, Date];
		const newRange = newEnd.getTime() - newStart.getTime();
		const originalRange = endDate.getTime() - startDate.getTime();

		// Zooming in should decrease the range
		expect(newRange).toBeLessThan(originalRange);
	});

	it("respects minimum zoom level", () => {
		const startDate = new Date("2024-01-01T00:00:00");
		const endDate = new Date("2024-01-01T01:30:00"); // 1.5 hour range (close to min)
		const onZoomChange = vi.fn();
		const minSeconds = 3599; // ~1 hour

		const { result } = renderHook(() =>
			useChartZoom({ startDate, endDate, onZoomChange, minSeconds }),
		);

		const mockElement = document.createElement("div");
		mockElement.getBoundingClientRect = mockGetBoundingClientRect;
		Object.defineProperty(result.current.containerRef, "current", {
			value: mockElement,
			writable: true,
		});

		// Try to zoom in multiple times
		for (let i = 0; i < 10; i++) {
			const wheelEvent = createMockWheelEvent(-100, 250);
			act(() => {
				result.current.handleWheel(wheelEvent);
			});
		}

		expect(onZoomChange).toHaveBeenCalled();
		const lastCall = onZoomChange.mock.calls[
			onZoomChange.mock.calls.length - 1
		] as [Date, Date];
		const [newStart, newEnd] = lastCall;
		const newRangeSeconds = (newEnd.getTime() - newStart.getTime()) / 1000;

		// Should not go below minimum
		expect(newRangeSeconds).toBeGreaterThanOrEqual(minSeconds);
	});

	it("respects maximum zoom level", () => {
		const startDate = new Date("2024-01-01T00:00:00");
		const endDate = new Date("2024-01-06T00:00:00"); // 5 day range (close to max)
		const onZoomChange = vi.fn();
		const maxSeconds = 604799; // ~1 week

		const { result } = renderHook(() =>
			useChartZoom({ startDate, endDate, onZoomChange, maxSeconds }),
		);

		const mockElement = document.createElement("div");
		mockElement.getBoundingClientRect = mockGetBoundingClientRect;
		Object.defineProperty(result.current.containerRef, "current", {
			value: mockElement,
			writable: true,
		});

		// Try to zoom out multiple times
		for (let i = 0; i < 10; i++) {
			const wheelEvent = createMockWheelEvent(100, 250);
			act(() => {
				result.current.handleWheel(wheelEvent);
			});
		}

		expect(onZoomChange).toHaveBeenCalled();
		const lastCall = onZoomChange.mock.calls[
			onZoomChange.mock.calls.length - 1
		] as [Date, Date];
		const [newStart, newEnd] = lastCall;
		const newRangeSeconds = (newEnd.getTime() - newStart.getTime()) / 1000;

		// Should not exceed maximum
		expect(newRangeSeconds).toBeLessThanOrEqual(maxSeconds);
	});

	it("does not call onZoomChange when containerRef is not set", () => {
		const startDate = new Date("2024-01-01T00:00:00");
		const endDate = new Date("2024-01-02T00:00:00");
		const onZoomChange = vi.fn();

		const { result } = renderHook(() =>
			useChartZoom({ startDate, endDate, onZoomChange }),
		);

		const wheelEvent = createMockWheelEvent(100, 250);

		act(() => {
			result.current.handleWheel(wheelEvent);
		});

		expect(onZoomChange).not.toHaveBeenCalled();
	});

	it("centers zoom on mouse position", () => {
		const startDate = new Date("2024-01-01T00:00:00");
		const endDate = new Date("2024-01-01T12:00:00"); // 12 hour range
		const onZoomChange = vi.fn();

		const { result } = renderHook(() =>
			useChartZoom({ startDate, endDate, onZoomChange }),
		);

		const mockElement = document.createElement("div");
		mockElement.getBoundingClientRect = mockGetBoundingClientRect;
		Object.defineProperty(result.current.containerRef, "current", {
			value: mockElement,
			writable: true,
		});

		// Zoom at left edge (clientX = 0)
		const leftWheelEvent = createMockWheelEvent(-100, 0);
		act(() => {
			result.current.handleWheel(leftWheelEvent);
		});

		const [leftStart] = onZoomChange.mock.calls[0] as [Date, Date];

		// Reset and zoom at right edge (clientX = 500)
		onZoomChange.mockClear();

		const { result: result2 } = renderHook(() =>
			useChartZoom({ startDate, endDate, onZoomChange }),
		);

		const mockElement2 = document.createElement("div");
		mockElement2.getBoundingClientRect = mockGetBoundingClientRect;
		Object.defineProperty(result2.current.containerRef, "current", {
			value: mockElement2,
			writable: true,
		});

		const rightWheelEvent = createMockWheelEvent(-100, 500);
		act(() => {
			result2.current.handleWheel(rightWheelEvent);
		});

		const [rightStart] = onZoomChange.mock.calls[0] as [Date, Date];

		// When zooming at left edge, start should change less than when zooming at right edge
		const leftStartDelta = Math.abs(leftStart.getTime() - startDate.getTime());
		const rightStartDelta = Math.abs(
			rightStart.getTime() - startDate.getTime(),
		);

		expect(leftStartDelta).toBeLessThan(rightStartDelta);
	});

	it("updates when input dates change", () => {
		const startDate = new Date("2024-01-01T00:00:00");
		const endDate = new Date("2024-01-02T00:00:00");
		const newEndDate = new Date("2024-01-03T00:00:00");
		const onZoomChange = vi.fn();

		const { result, rerender } = renderHook(
			({ start, end }) =>
				useChartZoom({ startDate: start, endDate: end, onZoomChange }),
			{
				initialProps: { start: startDate, end: endDate },
			},
		);

		const mockElement = document.createElement("div");
		mockElement.getBoundingClientRect = mockGetBoundingClientRect;
		Object.defineProperty(result.current.containerRef, "current", {
			value: mockElement,
			writable: true,
		});

		// Rerender with new end date
		rerender({ start: startDate, end: newEndDate });

		const wheelEvent = createMockWheelEvent(100, 250);
		act(() => {
			result.current.handleWheel(wheelEvent);
		});

		expect(onZoomChange).toHaveBeenCalled();
		const [, newEnd] = onZoomChange.mock.calls[0] as [Date, Date];

		// The new end should be based on the updated endDate
		expect(newEnd.getTime()).toBeGreaterThan(endDate.getTime());
	});
});
