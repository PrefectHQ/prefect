import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { getDateRangeFromSearch } from "./dashboard";

const NOW = new Date("2024-06-01T12:00:00.000Z");

describe("getDateRangeFromSearch", () => {
	beforeEach(() => {
		vi.useFakeTimers();
		vi.setSystemTime(NOW);
	});

	afterEach(() => {
		vi.useRealTimers();
	});

	it("recomputes relative spans instead of using stale from/to", () => {
		expect(
			getDateRangeFromSearch({
				rangeType: "span",
				seconds: -3600,
				from: "2020-01-01T00:00:00.000Z",
				to: "2020-01-01T01:00:00.000Z",
			}),
		).toEqual({
			from: "2024-06-01T11:00:00.000Z",
			to: "2024-06-01T12:00:00.000Z",
		});
	});

	it("honors explicit from/to when no range type is set", () => {
		expect(
			getDateRangeFromSearch({
				seconds: -3600,
				from: "2020-01-01T00:00:00.000Z",
				to: "2020-01-01T01:00:00.000Z",
			}),
		).toEqual({
			from: "2020-01-01T00:00:00.000Z",
			to: "2020-01-01T01:00:00.000Z",
		});
	});
});
