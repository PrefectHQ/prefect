import { afterEach, describe, expect, it, vi } from "vitest";
import { dateRangeValueToUrlState } from "./date-range-url-state";

describe("dateRangeValueToUrlState", () => {
	afterEach(() => vi.useRealTimers());

	it("keeps the next hour as a future range", () => {
		vi.useFakeTimers({ now: new Date("2026-01-01T12:00:00Z") });

		expect(dateRangeValueToUrlState({ type: "span", seconds: 3600 })).toEqual({
			start: "2026-01-01T12:00:00.000Z",
			end: "2026-01-01T13:00:00.000Z",
		});
	});
});
