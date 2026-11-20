import { describe, expect, it } from "vitest";
import {
	buildStateFilter,
	parseStateNames,
	serializeStateNames,
} from "./state-filter-utils";

describe("state filters", () => {
	it("preserves legacy URLs and exact custom names", () => {
		expect(parseStateNames("Failed,Baseline NOT Met")).toEqual([
			"Failed",
			"Baseline NOT Met",
		]);
		const names = ["Baseline, NOT Met", "baseline NOT Met"];
		expect(parseStateNames(serializeStateNames(names))).toEqual(names);
	});
	it("combines names and types with AND and alternatives with OR", () => {
		expect(
			buildStateFilter(["Baseline NOT Met", "TimedOut"], ["FAILED", "CRASHED"]),
		).toEqual({
			operator: "and_",
			name: { any_: ["Baseline NOT Met", "TimedOut"] },
			type: { any_: ["FAILED", "CRASHED"] },
		});
		expect(buildStateFilter([], [])).toBeUndefined();
	});
});
