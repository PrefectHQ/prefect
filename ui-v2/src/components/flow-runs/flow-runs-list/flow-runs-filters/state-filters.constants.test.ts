import { describe, expect, it } from "vitest";
import { buildApiStateFilterFromSelections } from "./state-filters.constants";

describe("buildApiStateFilterFromSelections", () => {
	it("maps canonical Failed to FAILED state type", () => {
		expect(buildApiStateFilterFromSelections(["Failed"], [])).toEqual({
			operator: "and_",
			type: { any_: ["FAILED"] },
		});
	});

	it("deduplicates types shared by TimedOut and Failed", () => {
		expect(
			buildApiStateFilterFromSelections(["Failed", "TimedOut"], []),
		).toEqual({
			operator: "and_",
			type: { any_: ["FAILED"] },
		});
	});

	it("combines state types with custom state names", () => {
		expect(
			buildApiStateFilterFromSelections(["Failed"], ["NewObjects"]),
		).toEqual({
			operator: "and_",
			type: { any_: ["FAILED"] },
			name: { any_: ["NewObjects"] },
		});
	});

	it("uses or_ when both state types and specific names apply (e.g. Failed and Late)", () => {
		expect(buildApiStateFilterFromSelections(["Failed", "Late"], [])).toEqual({
			operator: "or_",
			type: { any_: ["FAILED"] },
			name: { any_: ["Late"] },
		});
	});

	it("returns undefined when nothing selected", () => {
		expect(buildApiStateFilterFromSelections([], [])).toBeUndefined();
		expect(buildApiStateFilterFromSelections([], ["  "])).toBeUndefined();
	});

	it("trims custom state names", () => {
		expect(buildApiStateFilterFromSelections([], ["  NewObjects  "])).toEqual({
			operator: "and_",
			name: { any_: ["NewObjects"] },
		});
	});
});
