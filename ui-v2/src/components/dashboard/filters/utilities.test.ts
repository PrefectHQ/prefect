import { describe, expect, test } from "vitest";
import type {
	DateRangeSelectAroundValue,
	DateRangeSelectPeriodValue,
	DateRangeSelectRangeValue,
	DateRangeSelectSpanValue,
} from "./types";
import {
	getDateRangeLabel,
	getSpanLabel,
	isValidDateRange,
	mapDateRangeToDateRange,
	PRESET_RANGES,
} from "./utilities";

describe("getSpanLabel", () => {
	test("returns correct labels for common durations", () => {
		expect(getSpanLabel(3600)).toBe("1 hour");
		expect(getSpanLabel(86400)).toBe("1 day");
		expect(getSpanLabel(604800)).toBe("7 days");
		expect(getSpanLabel(2592000)).toBe("30 days");
		expect(getSpanLabel(7776000)).toBe("90 days");
	});

	test("handles singular and plural forms", () => {
		expect(getSpanLabel(1)).toBe("1 second");
		expect(getSpanLabel(2)).toBe("2 seconds");
		expect(getSpanLabel(60)).toBe("1 minute");
		expect(getSpanLabel(120)).toBe("2 minutes");
	});

	test("handles absolute values for negative seconds", () => {
		expect(getSpanLabel(-3600)).toBe("1 hour");
		expect(getSpanLabel(-86400)).toBe("1 day");
	});
});

describe("getDateRangeLabel", () => {
	test("returns empty string for null/undefined values", () => {
		expect(getDateRangeLabel(null)).toBe("");
		expect(getDateRangeLabel(undefined)).toBe("");
	});

	test("returns correct label for span values", () => {
		const spanValue: DateRangeSelectSpanValue = {
			type: "span",
			seconds: -86400,
		};
		expect(getDateRangeLabel(spanValue)).toBe("1 day");
	});

	test("returns correct label for range values", () => {
		const rangeValue: DateRangeSelectRangeValue = {
			type: "range",
			startDate: new Date("2024-01-01"),
			endDate: new Date("2024-01-31"),
		};
		expect(getDateRangeLabel(rangeValue)).toBe("Jan 1, 2024 - Jan 31, 2024");
	});

	test("returns correct label for period values", () => {
		const periodValue: DateRangeSelectPeriodValue = {
			type: "period",
			period: "Today",
		};
		expect(getDateRangeLabel(periodValue)).toBe("Today");
	});

	test("returns correct label for around values", () => {
		const aroundValue: DateRangeSelectAroundValue = {
			type: "around",
			date: new Date("2024-01-15"),
			quantity: 2,
			unit: "day",
		};
		expect(getDateRangeLabel(aroundValue)).toBe("2 days around Jan 15, 2024");

		const aroundValueSingular: DateRangeSelectAroundValue = {
			type: "around",
			date: new Date("2024-01-15"),
			quantity: 1,
			unit: "hour",
		};
		expect(getDateRangeLabel(aroundValueSingular)).toBe(
			"1 hour around Jan 15, 2024",
		);
	});
});

describe("mapDateRangeToDateRange", () => {
	test("returns null for null/undefined values", () => {
		expect(mapDateRangeToDateRange(null)).toBe(null);
		expect(mapDateRangeToDateRange(undefined)).toBe(null);
	});

	test("correctly maps span values", () => {
		const spanValue: DateRangeSelectSpanValue = {
			type: "span",
			seconds: -3600,
		};
		const result = mapDateRangeToDateRange(spanValue);

		expect(result).not.toBe(null);
		if (result) {
			expect(result.timeSpanInSeconds).toBe(3600);
			expect(result.endDate.getTime() - result.startDate.getTime()).toBe(
				3600 * 1000,
			);
		}
	});

	test("correctly maps range values", () => {
		const startDate = new Date("2024-01-01T00:00:00Z");
		const endDate = new Date("2024-01-02T00:00:00Z");
		const rangeValue: DateRangeSelectRangeValue = {
			type: "range",
			startDate,
			endDate,
		};

		const result = mapDateRangeToDateRange(rangeValue);
		expect(result).not.toBe(null);
		if (result) {
			expect(result.startDate).toEqual(startDate);
			expect(result.endDate).toEqual(endDate);
			expect(result.timeSpanInSeconds).toBe(86400); // 24 hours
		}
	});

	test("correctly maps period values for Today", () => {
		const periodValue: DateRangeSelectPeriodValue = {
			type: "period",
			period: "Today",
		};
		const result = mapDateRangeToDateRange(periodValue);

		expect(result).not.toBe(null);
		if (result) {
			expect(result.timeSpanInSeconds).toBe(86400);
		}
	});

	test("correctly maps around values", () => {
		const date = new Date("2024-01-15T12:00:00Z");
		const aroundValue: DateRangeSelectAroundValue = {
			type: "around",
			date,
			quantity: 2,
			unit: "hour",
		};

		const result = mapDateRangeToDateRange(aroundValue);
		expect(result).not.toBe(null);
		if (result) {
			expect(result.timeSpanInSeconds).toBe(7200 * 2); // 2 hours * 2 (before and after)
			expect(result.startDate.getTime()).toBe(date.getTime() - 7200 * 1000);
			expect(result.endDate.getTime()).toBe(date.getTime() + 7200 * 1000);
		}
	});
});

describe("isValidDateRange", () => {
	test("returns valid for null/undefined values", () => {
		expect(isValidDateRange(null)).toEqual({ valid: true });
		expect(isValidDateRange(undefined)).toEqual({ valid: true });
	});

	test("validates against min date", () => {
		const minDate = new Date("2024-01-01");
		const beforeMin: DateRangeSelectRangeValue = {
			type: "range",
			startDate: new Date("2023-12-31"),
			endDate: new Date("2024-01-02"),
		};

		const result = isValidDateRange(beforeMin, minDate);
		expect(result.valid).toBe(false);
		expect(result.reason).toContain("Start date cannot be before");
	});

	test("validates against max date", () => {
		const maxDate = new Date("2024-12-31");
		const afterMax: DateRangeSelectRangeValue = {
			type: "range",
			startDate: new Date("2024-01-01"),
			endDate: new Date("2025-01-01"),
		};

		const result = isValidDateRange(afterMax, undefined, maxDate);
		expect(result.valid).toBe(false);
		expect(result.reason).toContain("End date cannot be after");
	});

	test("returns valid for ranges within bounds", () => {
		const minDate = new Date("2024-01-01");
		const maxDate = new Date("2024-12-31");
		const validRange: DateRangeSelectRangeValue = {
			type: "range",
			startDate: new Date("2024-06-01"),
			endDate: new Date("2024-06-30"),
		};

		const result = isValidDateRange(validRange, minDate, maxDate);
		expect(result.valid).toBe(true);
	});
});

describe("PRESET_RANGES", () => {
	test("contains expected preset ranges", () => {
		expect(PRESET_RANGES).toHaveLength(5);

		const labels = PRESET_RANGES.map((preset) => preset.label);
		expect(labels).toContain("Last hour");
		expect(labels).toContain("Last day");
		expect(labels).toContain("Last 7 days");
		expect(labels).toContain("Last 30 days");
		expect(labels).toContain("Last 90 days");
	});

	test("all presets have span type with negative seconds", () => {
		PRESET_RANGES.forEach((preset) => {
			expect(preset.value.type).toBe("span");
			expect(preset.value.seconds).toBeLessThan(0);
		});
	});
});
