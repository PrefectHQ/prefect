import { describe, expect, it } from "vitest";
import { getDateRangeFromSearch } from "./dashboard";

describe("getDateRangeFromSearch", () => {
	it("recomputes relative spans instead of using stale from/to", () => {
		const { from, to } = getDateRangeFromSearch({
			rangeType: "span",
			seconds: -3600,
			from: "2020-01-01T00:00:00.000Z",
			to: "2020-01-01T01:00:00.000Z",
		});

		expect(new Date(to).getTime() - new Date(from).getTime()).toBe(3600 * 1000);
		expect(new Date(to).getTime()).toBeGreaterThan(Date.now() - 2 * 60 * 1000);
	});

	it("honors explicit from/to when no range type is set", () => {
		expect(
			getDateRangeFromSearch({
				from: "2020-01-01T00:00:00.000Z",
				to: "2020-01-01T01:00:00.000Z",
			}),
		).toEqual({
			from: "2020-01-01T00:00:00.000Z",
			to: "2020-01-01T01:00:00.000Z",
		});
	});
});
