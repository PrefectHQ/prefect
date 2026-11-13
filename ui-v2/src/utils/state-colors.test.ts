import { afterEach, describe, expect, test, vi } from "vitest";
import { getAllStateColors, getStateColor, STATE_COLORS } from "./state-colors";

afterEach(() => {
	vi.restoreAllMocks();
});

describe("STATE_COLORS", () => {
	test("should have all state types defined", () => {
		const expectedStates = [
			"COMPLETED",
			"FAILED",
			"RUNNING",
			"CANCELLED",
			"CANCELLING",
			"CRASHED",
			"PAUSED",
			"PENDING",
			"SCHEDULED",
		];

		for (const state of expectedStates) {
			expect(STATE_COLORS[state as keyof typeof STATE_COLORS]).toBeDefined();
		}
	});

	test("should have hex color values", () => {
		const hexColorRegex = /^#[0-9A-Fa-f]{6}$/;

		for (const color of Object.values(STATE_COLORS)) {
			expect(color).toMatch(hexColorRegex);
		}
	});

	test("should have correct default colors", () => {
		expect(STATE_COLORS.COMPLETED).toBe("#219D4B");
		expect(STATE_COLORS.FAILED).toBe("#DE0529");
		expect(STATE_COLORS.RUNNING).toBe("#09439B");
		expect(STATE_COLORS.CANCELLED).toBe("#333333");
		expect(STATE_COLORS.CANCELLING).toBe("#334863");
		expect(STATE_COLORS.CRASHED).toBe("#EA580C");
		expect(STATE_COLORS.PAUSED).toBe("#726576");
		expect(STATE_COLORS.PENDING).toBe("#8E8093");
		expect(STATE_COLORS.SCHEDULED).toBe("#E08504");
	});
});

describe("getStateColor", () => {
	test("should return fallback color when document is undefined", () => {
		// @ts-expect-error - intentionally returning undefined to simulate server rendering
		vi.spyOn(globalThis, "document", "get").mockReturnValueOnce(undefined);

		const RESULT = getStateColor("COMPLETED");
		const EXPECTED = STATE_COLORS.COMPLETED;

		expect(RESULT).toEqual(EXPECTED);
	});

	test("should return CSS variable value when available", () => {
		const mockColor = "#00ff00";
		vi.spyOn(CSSStyleDeclaration.prototype, "getPropertyValue").mockReturnValue(
			mockColor,
		);

		const RESULT = getStateColor("COMPLETED");

		expect(RESULT).toEqual(mockColor);
	});

	test("should return fallback color when CSS variable is empty", () => {
		vi.spyOn(CSSStyleDeclaration.prototype, "getPropertyValue").mockReturnValue(
			"",
		);

		const RESULT = getStateColor("FAILED");
		const EXPECTED = STATE_COLORS.FAILED;

		expect(RESULT).toEqual(EXPECTED);
	});

	test("should use correct CSS variable name with default shade", () => {
		const mockGetPropertyValue = vi
			.spyOn(CSSStyleDeclaration.prototype, "getPropertyValue")
			.mockReturnValue("#123456");

		getStateColor("RUNNING");

		expect(mockGetPropertyValue).toHaveBeenCalledWith("--state-running-600");
	});

	test("should use correct CSS variable name with custom shade", () => {
		const mockGetPropertyValue = vi
			.spyOn(CSSStyleDeclaration.prototype, "getPropertyValue")
			.mockReturnValue("#123456");

		getStateColor("SCHEDULED", 500);

		expect(mockGetPropertyValue).toHaveBeenCalledWith("--state-scheduled-500");
	});

	test("should trim whitespace from CSS variable value", () => {
		vi.spyOn(CSSStyleDeclaration.prototype, "getPropertyValue").mockReturnValue(
			"  #abcdef  ",
		);

		const RESULT = getStateColor("PAUSED");

		expect(RESULT).toEqual("#abcdef");
	});
});

describe("getAllStateColors", () => {
	test("should return all state colors", () => {
		vi.spyOn(CSSStyleDeclaration.prototype, "getPropertyValue").mockReturnValue(
			"",
		);

		const RESULT = getAllStateColors();

		expect(Object.keys(RESULT)).toHaveLength(9);
		expect(RESULT.COMPLETED).toBeDefined();
		expect(RESULT.FAILED).toBeDefined();
		expect(RESULT.RUNNING).toBeDefined();
		expect(RESULT.CANCELLED).toBeDefined();
		expect(RESULT.CANCELLING).toBeDefined();
		expect(RESULT.CRASHED).toBeDefined();
		expect(RESULT.PAUSED).toBeDefined();
		expect(RESULT.PENDING).toBeDefined();
		expect(RESULT.SCHEDULED).toBeDefined();
	});

	test("should use default shade of 600", () => {
		const mockGetPropertyValue = vi
			.spyOn(CSSStyleDeclaration.prototype, "getPropertyValue")
			.mockReturnValue("");

		getAllStateColors();

		expect(mockGetPropertyValue).toHaveBeenCalledWith("--state-completed-600");
		expect(mockGetPropertyValue).toHaveBeenCalledWith("--state-failed-600");
	});

	test("should use custom shade when provided", () => {
		const mockGetPropertyValue = vi
			.spyOn(CSSStyleDeclaration.prototype, "getPropertyValue")
			.mockReturnValue("");

		getAllStateColors(500);

		expect(mockGetPropertyValue).toHaveBeenCalledWith("--state-completed-500");
		expect(mockGetPropertyValue).toHaveBeenCalledWith("--state-failed-500");
	});

	test("should return fallback colors when CSS variables are not available", () => {
		vi.spyOn(CSSStyleDeclaration.prototype, "getPropertyValue").mockReturnValue(
			"",
		);

		const RESULT = getAllStateColors();

		expect(RESULT.COMPLETED).toEqual(STATE_COLORS.COMPLETED);
		expect(RESULT.FAILED).toEqual(STATE_COLORS.FAILED);
		expect(RESULT.RUNNING).toEqual(STATE_COLORS.RUNNING);
	});
});
