import { beforeEach, describe, expect, test, vi } from "vitest";
import { getAllStateColors, getStateColor, STATE_COLORS } from "./state-colors";

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
	beforeEach(() => {
		vi.restoreAllMocks();
	});

	test("should return fallback color when document is undefined", () => {
		const originalDocument = globalThis.document;
		// @ts-expect-error - intentionally setting document to undefined for testing
		globalThis.document = undefined;

		const RESULT = getStateColor("COMPLETED");
		const EXPECTED = STATE_COLORS.COMPLETED;

		expect(RESULT).toEqual(EXPECTED);

		globalThis.document = originalDocument;
	});

	test("should return CSS variable value when available", () => {
		const mockColor = "#00ff00";
		const mockGetComputedStyle = vi.fn().mockReturnValue({
			getPropertyValue: vi.fn().mockReturnValue(mockColor),
		});
		vi.stubGlobal("getComputedStyle", mockGetComputedStyle);

		const RESULT = getStateColor("COMPLETED");

		expect(RESULT).toEqual(mockColor);
		expect(mockGetComputedStyle).toHaveBeenCalledWith(document.documentElement);
	});

	test("should return fallback color when CSS variable is empty", () => {
		const mockGetComputedStyle = vi.fn().mockReturnValue({
			getPropertyValue: vi.fn().mockReturnValue(""),
		});
		vi.stubGlobal("getComputedStyle", mockGetComputedStyle);

		const RESULT = getStateColor("FAILED");
		const EXPECTED = STATE_COLORS.FAILED;

		expect(RESULT).toEqual(EXPECTED);
	});

	test("should use correct CSS variable name with default shade", () => {
		const mockGetPropertyValue = vi.fn().mockReturnValue("#123456");
		const mockGetComputedStyle = vi.fn().mockReturnValue({
			getPropertyValue: mockGetPropertyValue,
		});
		vi.stubGlobal("getComputedStyle", mockGetComputedStyle);

		getStateColor("RUNNING");

		expect(mockGetPropertyValue).toHaveBeenCalledWith("--state-running-600");
	});

	test("should use correct CSS variable name with custom shade", () => {
		const mockGetPropertyValue = vi.fn().mockReturnValue("#123456");
		const mockGetComputedStyle = vi.fn().mockReturnValue({
			getPropertyValue: mockGetPropertyValue,
		});
		vi.stubGlobal("getComputedStyle", mockGetComputedStyle);

		getStateColor("SCHEDULED", 500);

		expect(mockGetPropertyValue).toHaveBeenCalledWith("--state-scheduled-500");
	});

	test("should trim whitespace from CSS variable value", () => {
		const mockGetComputedStyle = vi.fn().mockReturnValue({
			getPropertyValue: vi.fn().mockReturnValue("  #abcdef  "),
		});
		vi.stubGlobal("getComputedStyle", mockGetComputedStyle);

		const RESULT = getStateColor("PAUSED");

		expect(RESULT).toEqual("#abcdef");
	});
});

describe("getAllStateColors", () => {
	beforeEach(() => {
		vi.restoreAllMocks();
	});

	test("should return all state colors", () => {
		const mockGetComputedStyle = vi.fn().mockReturnValue({
			getPropertyValue: vi.fn().mockReturnValue(""),
		});
		vi.stubGlobal("getComputedStyle", mockGetComputedStyle);

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
		const mockGetPropertyValue = vi.fn().mockReturnValue("");
		const mockGetComputedStyle = vi.fn().mockReturnValue({
			getPropertyValue: mockGetPropertyValue,
		});
		vi.stubGlobal("getComputedStyle", mockGetComputedStyle);

		getAllStateColors();

		expect(mockGetPropertyValue).toHaveBeenCalledWith("--state-completed-600");
		expect(mockGetPropertyValue).toHaveBeenCalledWith("--state-failed-600");
	});

	test("should use custom shade when provided", () => {
		const mockGetPropertyValue = vi.fn().mockReturnValue("");
		const mockGetComputedStyle = vi.fn().mockReturnValue({
			getPropertyValue: mockGetPropertyValue,
		});
		vi.stubGlobal("getComputedStyle", mockGetComputedStyle);

		getAllStateColors(500);

		expect(mockGetPropertyValue).toHaveBeenCalledWith("--state-completed-500");
		expect(mockGetPropertyValue).toHaveBeenCalledWith("--state-failed-500");
	});

	test("should return fallback colors when CSS variables are not available", () => {
		const mockGetComputedStyle = vi.fn().mockReturnValue({
			getPropertyValue: vi.fn().mockReturnValue(""),
		});
		vi.stubGlobal("getComputedStyle", mockGetComputedStyle);

		const RESULT = getAllStateColors();

		expect(RESULT.COMPLETED).toEqual(STATE_COLORS.COMPLETED);
		expect(RESULT.FAILED).toEqual(STATE_COLORS.FAILED);
		expect(RESULT.RUNNING).toEqual(STATE_COLORS.RUNNING);
	});
});
