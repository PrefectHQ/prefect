import { describe, expect, it } from "vitest";
import {
	isPausedState,
	isRunningState,
	isStuckState,
	isTerminalState,
	STUCK_STATES,
	TERMINAL_STATES,
} from "./state-utilities";

describe("state-utilities", () => {
	describe("isStuckState", () => {
		it.each([
			"RUNNING",
			"SCHEDULED",
			"PENDING",
			"PAUSED",
		] as const)("returns true for %s", (state) => {
			expect(isStuckState(state)).toBe(true);
		});

		it.each([
			"COMPLETED",
			"FAILED",
			"CANCELLED",
			"CRASHED",
		] as const)("returns false for terminal state %s", (state) => {
			expect(isStuckState(state)).toBe(false);
		});

		it("returns false for null", () => {
			expect(isStuckState(null)).toBe(false);
		});

		it("returns false for undefined", () => {
			expect(isStuckState(undefined)).toBe(false);
		});
	});

	describe("isRunningState", () => {
		it("returns true for RUNNING", () => {
			expect(isRunningState("RUNNING")).toBe(true);
		});

		it.each([
			"SCHEDULED",
			"PENDING",
			"PAUSED",
			"COMPLETED",
			"FAILED",
		] as const)("returns false for %s", (state) => {
			expect(isRunningState(state)).toBe(false);
		});
	});

	describe("isPausedState", () => {
		it("returns true for PAUSED", () => {
			expect(isPausedState("PAUSED")).toBe(true);
		});

		it.each([
			"RUNNING",
			"SCHEDULED",
			"COMPLETED",
			"FAILED",
		] as const)("returns false for %s", (state) => {
			expect(isPausedState(state)).toBe(false);
		});
	});

	describe("isTerminalState", () => {
		it.each([
			"COMPLETED",
			"FAILED",
			"CANCELLED",
			"CRASHED",
		] as const)("returns true for %s", (state) => {
			expect(isTerminalState(state)).toBe(true);
		});

		it.each([
			"RUNNING",
			"SCHEDULED",
			"PENDING",
			"PAUSED",
		] as const)("returns false for non-terminal state %s", (state) => {
			expect(isTerminalState(state)).toBe(false);
		});
	});

	describe("constants", () => {
		it("STUCK_STATES contains expected values", () => {
			expect(STUCK_STATES).toEqual([
				"RUNNING",
				"SCHEDULED",
				"PENDING",
				"PAUSED",
			]);
		});

		it("TERMINAL_STATES contains expected values", () => {
			expect(TERMINAL_STATES).toEqual([
				"COMPLETED",
				"FAILED",
				"CANCELLED",
				"CRASHED",
			]);
		});
	});
});
