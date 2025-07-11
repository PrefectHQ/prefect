import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { useStepper } from "./use-stepper";

const TOTAL_NUM_STEPS = 3;

describe("useStepper()", () => {
	it("incrementStep() to the next available step", () => {
		// Setup
		const { result } = renderHook(() => useStepper(TOTAL_NUM_STEPS));

		// Update State
		act(() => result.current.incrementStep());

		// Asserts
		expect(result.current.currentStep).toEqual(1);
	});

	it("incrementStep() does not increment at final step", () => {
		// Setup
		const { result } = renderHook(() => useStepper(TOTAL_NUM_STEPS, 2));

		// Update State
		act(() => result.current.incrementStep());

		// Asserts
		expect(result.current.currentStep).toEqual(2);
	});

	it("decrementStep() to the previous available step", () => {
		// Setup
		const { result } = renderHook(() => useStepper(TOTAL_NUM_STEPS, 2));

		// Update State
		act(() => result.current.decrementStep());

		// Asserts
		expect(result.current.currentStep).toEqual(1);
	});

	it("decrementStep() does not decrement at first step", () => {
		// Setup
		const { result } = renderHook(() => useStepper(TOTAL_NUM_STEPS));

		// Update State
		act(() => result.current.decrementStep());

		// Asserts
		expect(result.current.currentStep).toEqual(0);
	});

	it("isFinalStep returns true if its the final step", () => {
		// Setup
		const { result } = renderHook(() => useStepper(TOTAL_NUM_STEPS, 2));

		// Asserts
		expect(result.current.isFinalStep).toBe(true);
	});
	it("isFinalStep returns false if its the final step", () => {
		// Setup
		const { result } = renderHook(() => useStepper(TOTAL_NUM_STEPS));

		// Asserts
		expect(result.current.isFinalStep).toBe(false);
	});

	it("isStartingStep returns true if its the first step", () => {
		// Setup
		const { result } = renderHook(() => useStepper(TOTAL_NUM_STEPS));

		// Asserts
		expect(result.current.isStartingStep).toBe(true);
	});
	it("isStartingStep returns false if its the final step", () => {
		// Setup
		const { result } = renderHook(() => useStepper(TOTAL_NUM_STEPS, 1));

		// Asserts
		expect(result.current.isStartingStep).toBe(false);
	});

	it("reset() returns to the initial step", () => {
		// Setup
		const { result } = renderHook(() => useStepper(TOTAL_NUM_STEPS, 1));

		// Update State
		act(() => result.current.decrementStep());

		// Asserts
		expect(result.current.currentStep).toEqual(0);

		// Update State
		act(() => result.current.reset());

		// Asserts
		expect(result.current.currentStep).toEqual(1);
	});

	it("completedStepsSet returns set of steps that has been completed", () => {
		// Setup
		const { result } = renderHook(() => useStepper(TOTAL_NUM_STEPS));

		// Update State
		// Finish step 0
		act(() => result.current.incrementStep());
		// Finish Step 1
		act(() => result.current.incrementStep());

		// Asserts
		expect(result.current.completedStepsSet.has(0)).toBe(true);
		expect(result.current.completedStepsSet.has(1)).toBe(true);
		expect(result.current.completedStepsSet.has(2)).toBe(false);
	});

	it("visitedStepsSet returns set of steps that has been visited", () => {
		// Setup
		const { result } = renderHook(() => useStepper(TOTAL_NUM_STEPS));

		// Update State
		// Visit step 1
		act(() => result.current.incrementStep());
		// Visit step 2
		act(() => result.current.incrementStep());

		// Asserts
		expect(result.current.visitedStepsSet.has(0)).toBe(true);
		expect(result.current.visitedStepsSet.has(1)).toBe(true);
		expect(result.current.visitedStepsSet.has(2)).toBe(true);
	});
});
