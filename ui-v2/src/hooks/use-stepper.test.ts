import { act, renderHook } from "@testing-library/react";
import { useStepper } from "./use-stepper";

import { describe, expect, it } from "vitest";

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

	it("getIsCurrentStep() returns true if its the correct step", () => {
		// Setup
		const { result } = renderHook(() => useStepper(TOTAL_NUM_STEPS));

		// Asserts
		expect(result.current.getIsCurrentStep(0)).toBe(true);
	});
	it("getIsCurrentStep() returns false if its the correct step", () => {
		// Setup
		const { result } = renderHook(() => useStepper(TOTAL_NUM_STEPS));

		// Asserts
		expect(result.current.getIsCurrentStep(1)).toBe(false);
	});

	it("getIsStepCompleted() returns true if the step has been passed", () => {
		// Setup
		const { result } = renderHook(() => useStepper(TOTAL_NUM_STEPS, 1));

		// Asserts
		expect(result.current.getIsStepCompleted(0)).toBe(true);
	});

	it("getIsStepCompleted() returns false if the step has not been passed", () => {
		// Setup
		const { result } = renderHook(() => useStepper(TOTAL_NUM_STEPS, 1));

		// Asserts
		expect(result.current.getIsStepCompleted(1)).toBe(false);
		expect(result.current.getIsStepCompleted(2)).toBe(false);
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
});
