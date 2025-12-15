import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { useChartSelection } from "./use-chart-selection";

describe("useChartSelection", () => {
	const createMockMouseEvent = (
		clientX: number,
		button = 0,
	): React.MouseEvent => {
		return {
			clientX,
			button,
			preventDefault: vi.fn(),
		} as unknown as React.MouseEvent;
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

	it("returns selection state and event handlers", () => {
		const startDate = new Date("2024-01-01T00:00:00");
		const endDate = new Date("2024-01-02T00:00:00");

		const { result } = renderHook(() =>
			useChartSelection({ startDate, endDate }),
		);

		expect(result.current).toHaveProperty("containerRef");
		expect(result.current).toHaveProperty("selectionStart");
		expect(result.current).toHaveProperty("selectionEnd");
		expect(result.current).toHaveProperty("isDragging");
		expect(result.current).toHaveProperty("handleMouseDown");
		expect(result.current).toHaveProperty("handleMouseMove");
		expect(result.current).toHaveProperty("handleMouseUp");
		expect(result.current).toHaveProperty("handleMouseLeave");
		expect(result.current).toHaveProperty("clearSelection");
	});

	it("initializes with null selection and not dragging", () => {
		const startDate = new Date("2024-01-01T00:00:00");
		const endDate = new Date("2024-01-02T00:00:00");

		const { result } = renderHook(() =>
			useChartSelection({ startDate, endDate }),
		);

		expect(result.current.selectionStart).toBeNull();
		expect(result.current.selectionEnd).toBeNull();
		expect(result.current.isDragging).toBe(false);
	});

	it("starts dragging on mouse down with left button", () => {
		const startDate = new Date("2024-01-01T00:00:00");
		const endDate = new Date("2024-01-02T00:00:00");

		const { result } = renderHook(() =>
			useChartSelection({ startDate, endDate }),
		);

		const mockElement = document.createElement("div");
		mockElement.getBoundingClientRect = mockGetBoundingClientRect;
		Object.defineProperty(result.current.containerRef, "current", {
			value: mockElement,
			writable: true,
		});

		const mouseDownEvent = createMockMouseEvent(250, 0); // Left button

		act(() => {
			result.current.handleMouseDown(mouseDownEvent);
		});

		expect(result.current.isDragging).toBe(true);
		expect(result.current.selectionStart).not.toBeNull();
	});

	it("does not start dragging on right mouse button", () => {
		const startDate = new Date("2024-01-01T00:00:00");
		const endDate = new Date("2024-01-02T00:00:00");

		const { result } = renderHook(() =>
			useChartSelection({ startDate, endDate }),
		);

		const mockElement = document.createElement("div");
		mockElement.getBoundingClientRect = mockGetBoundingClientRect;
		Object.defineProperty(result.current.containerRef, "current", {
			value: mockElement,
			writable: true,
		});

		const mouseDownEvent = createMockMouseEvent(250, 2); // Right button

		act(() => {
			result.current.handleMouseDown(mouseDownEvent);
		});

		expect(result.current.isDragging).toBe(false);
		expect(result.current.selectionStart).toBeNull();
	});

	it("updates selection on mouse move while dragging", () => {
		const startDate = new Date("2024-01-01T00:00:00");
		const endDate = new Date("2024-01-02T00:00:00");

		const { result } = renderHook(() =>
			useChartSelection({ startDate, endDate }),
		);

		const mockElement = document.createElement("div");
		mockElement.getBoundingClientRect = mockGetBoundingClientRect;
		Object.defineProperty(result.current.containerRef, "current", {
			value: mockElement,
			writable: true,
		});

		// Start dragging at x=100
		act(() => {
			result.current.handleMouseDown(createMockMouseEvent(100, 0));
		});

		const initialSelectionStart = result.current.selectionStart;

		// Move to x=300
		act(() => {
			result.current.handleMouseMove(createMockMouseEvent(300));
		});

		expect(result.current.selectionEnd).not.toBeNull();
		expect(result.current.selectionEnd?.getTime()).not.toBe(
			initialSelectionStart?.getTime(),
		);
	});

	it("does not update selection on mouse move when not dragging", () => {
		const startDate = new Date("2024-01-01T00:00:00");
		const endDate = new Date("2024-01-02T00:00:00");

		const { result } = renderHook(() =>
			useChartSelection({ startDate, endDate }),
		);

		const mockElement = document.createElement("div");
		mockElement.getBoundingClientRect = mockGetBoundingClientRect;
		Object.defineProperty(result.current.containerRef, "current", {
			value: mockElement,
			writable: true,
		});

		// Move without starting drag
		act(() => {
			result.current.handleMouseMove(createMockMouseEvent(300));
		});

		expect(result.current.selectionStart).toBeNull();
		expect(result.current.selectionEnd).toBeNull();
	});

	it("finalizes selection on mouse up", () => {
		const startDate = new Date("2024-01-01T00:00:00");
		const endDate = new Date("2024-01-02T00:00:00");
		const onSelectionChange = vi.fn();

		const { result } = renderHook(() =>
			useChartSelection({ startDate, endDate, onSelectionChange }),
		);

		const mockElement = document.createElement("div");
		mockElement.getBoundingClientRect = mockGetBoundingClientRect;
		Object.defineProperty(result.current.containerRef, "current", {
			value: mockElement,
			writable: true,
		});

		// Start dragging at x=100
		act(() => {
			result.current.handleMouseDown(createMockMouseEvent(100, 0));
		});

		// Move to x=400 (significant distance for > 1 second selection)
		act(() => {
			result.current.handleMouseMove(createMockMouseEvent(400));
		});

		// Release
		act(() => {
			result.current.handleMouseUp();
		});

		expect(result.current.isDragging).toBe(false);
		expect(onSelectionChange).toHaveBeenCalled();
	});

	it("clears selection for sub-1-second selections", () => {
		// Use a 10-second time range so that 1px = 0.02 seconds
		// This ensures a 1px movement is less than 1 second
		const startDate = new Date("2024-01-01T12:00:00");
		const endDate = new Date("2024-01-01T12:00:10"); // 10 seconds later
		const onSelectionChange = vi.fn();

		const { result } = renderHook(() =>
			useChartSelection({ startDate, endDate, onSelectionChange }),
		);

		const mockElement = document.createElement("div");
		mockElement.getBoundingClientRect = mockGetBoundingClientRect;
		Object.defineProperty(result.current.containerRef, "current", {
			value: mockElement,
			writable: true,
		});

		// Start and end at nearly the same position (sub-1-second selection)
		// With 500px width and 10 second range, 1px = 0.02 seconds
		// So moving 10px = 0.2 seconds, which is less than 1 second
		act(() => {
			result.current.handleMouseDown(createMockMouseEvent(250, 0));
		});

		act(() => {
			result.current.handleMouseMove(createMockMouseEvent(260)); // 10px movement = 0.2 seconds
		});

		act(() => {
			result.current.handleMouseUp();
		});

		expect(result.current.selectionStart).toBeNull();
		expect(result.current.selectionEnd).toBeNull();
		expect(onSelectionChange).toHaveBeenCalledWith(null, null);
	});

	it("handles mouse leave as mouse up", () => {
		const startDate = new Date("2024-01-01T00:00:00");
		const endDate = new Date("2024-01-02T00:00:00");
		const onSelectionChange = vi.fn();

		const { result } = renderHook(() =>
			useChartSelection({ startDate, endDate, onSelectionChange }),
		);

		const mockElement = document.createElement("div");
		mockElement.getBoundingClientRect = mockGetBoundingClientRect;
		Object.defineProperty(result.current.containerRef, "current", {
			value: mockElement,
			writable: true,
		});

		// Start dragging
		act(() => {
			result.current.handleMouseDown(createMockMouseEvent(100, 0));
		});

		// Move
		act(() => {
			result.current.handleMouseMove(createMockMouseEvent(400));
		});

		// Leave container
		act(() => {
			result.current.handleMouseLeave();
		});

		expect(result.current.isDragging).toBe(false);
		expect(onSelectionChange).toHaveBeenCalled();
	});

	it("clears selection when clearSelection is called", () => {
		const startDate = new Date("2024-01-01T00:00:00");
		const endDate = new Date("2024-01-02T00:00:00");
		const onSelectionChange = vi.fn();

		const { result } = renderHook(() =>
			useChartSelection({ startDate, endDate, onSelectionChange }),
		);

		const mockElement = document.createElement("div");
		mockElement.getBoundingClientRect = mockGetBoundingClientRect;
		Object.defineProperty(result.current.containerRef, "current", {
			value: mockElement,
			writable: true,
		});

		// Create a selection
		act(() => {
			result.current.handleMouseDown(createMockMouseEvent(100, 0));
		});

		act(() => {
			result.current.handleMouseMove(createMockMouseEvent(400));
		});

		act(() => {
			result.current.handleMouseUp();
		});

		// Clear selection
		act(() => {
			result.current.clearSelection();
		});

		expect(result.current.selectionStart).toBeNull();
		expect(result.current.selectionEnd).toBeNull();
		expect(onSelectionChange).toHaveBeenLastCalledWith(null, null);
	});

	it("handles drag direction correctly (left to right)", () => {
		const startDate = new Date("2024-01-01T00:00:00");
		const endDate = new Date("2024-01-02T00:00:00");

		const { result } = renderHook(() =>
			useChartSelection({ startDate, endDate }),
		);

		const mockElement = document.createElement("div");
		mockElement.getBoundingClientRect = mockGetBoundingClientRect;
		Object.defineProperty(result.current.containerRef, "current", {
			value: mockElement,
			writable: true,
		});

		// Start at x=100, drag to x=400
		act(() => {
			result.current.handleMouseDown(createMockMouseEvent(100, 0));
		});

		act(() => {
			result.current.handleMouseMove(createMockMouseEvent(400));
		});

		// Selection start should be earlier than selection end
		expect(result.current.selectionStart).not.toBeNull();
		expect(result.current.selectionEnd).not.toBeNull();
		expect(result.current.selectionStart?.getTime()).toBeLessThan(
			result.current.selectionEnd?.getTime() ?? 0,
		);
	});

	it("handles drag direction correctly (right to left)", () => {
		const startDate = new Date("2024-01-01T00:00:00");
		const endDate = new Date("2024-01-02T00:00:00");

		const { result } = renderHook(() =>
			useChartSelection({ startDate, endDate }),
		);

		const mockElement = document.createElement("div");
		mockElement.getBoundingClientRect = mockGetBoundingClientRect;
		Object.defineProperty(result.current.containerRef, "current", {
			value: mockElement,
			writable: true,
		});

		// Start at x=400, drag to x=100
		act(() => {
			result.current.handleMouseDown(createMockMouseEvent(400, 0));
		});

		act(() => {
			result.current.handleMouseMove(createMockMouseEvent(100));
		});

		// Selection start should still be earlier than selection end
		expect(result.current.selectionStart).not.toBeNull();
		expect(result.current.selectionEnd).not.toBeNull();
		expect(result.current.selectionStart?.getTime()).toBeLessThan(
			result.current.selectionEnd?.getTime() ?? 0,
		);
	});

	it("works without onSelectionChange callback", () => {
		const startDate = new Date("2024-01-01T00:00:00");
		const endDate = new Date("2024-01-02T00:00:00");

		const { result } = renderHook(() =>
			useChartSelection({ startDate, endDate }),
		);

		const mockElement = document.createElement("div");
		mockElement.getBoundingClientRect = mockGetBoundingClientRect;
		Object.defineProperty(result.current.containerRef, "current", {
			value: mockElement,
			writable: true,
		});

		// Should not throw when no callback is provided
		expect(() => {
			act(() => {
				result.current.handleMouseDown(createMockMouseEvent(100, 0));
			});

			act(() => {
				result.current.handleMouseMove(createMockMouseEvent(400));
			});

			act(() => {
				result.current.handleMouseUp();
			});
		}).not.toThrow();
	});
});
