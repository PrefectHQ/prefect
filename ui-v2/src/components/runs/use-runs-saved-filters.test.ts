import { expect, it } from "vitest";
import {
	filterValuesToUrlParams,
	urlParamsToFilterValues,
} from "./use-runs-saved-filters";

it("restores legacy names and round-trips custom names with separate types", () => {
	expect(urlParamsToFilterValues({ state: "Failed,TimedOut" })).toEqual({
		state: ["Failed", "TimedOut"],
	});
	const saved = {
		state: ["Baseline, NOT Met", "baseline NOT Met"],
		stateTypes: ["FAILED" as const],
		range: "past-7-days" as const,
	};
	expect(urlParamsToFilterValues(filterValuesToUrlParams(saved))).toEqual(
		saved,
	);
});
