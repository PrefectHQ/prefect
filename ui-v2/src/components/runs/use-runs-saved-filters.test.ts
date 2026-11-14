/* eslint-disable @typescript-eslint/unbound-method */
import { expect, it, vi } from "vitest";
import {
	defaultFilterSearch,
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

const withStoredFilters = (
	defaultFilterId: string,
	savedFilters: unknown[],
	check: () => void,
) =>
	vi.mocked(localStorage.getItem).withImplementation(
		(key) =>
			({
				"prefect-ui-v2-default-filter-id": JSON.stringify(defaultFilterId),
				"prefect-ui-v2-saved-filters": JSON.stringify(savedFilters),
			})[key] ?? null,
		check,
	);

it("applies Past week to a runs URL without filters", () => {
	expect(defaultFilterSearch({ state: "", flows: "" })).toMatchObject({
		range: "past-7-days",
		page: 1,
		"task-runs-page": 1,
	});
});

it("applies the user's default saved filter, or Past week once it is deleted", () => {
	const mine = {
		id: "mine",
		name: "Failed this month",
		filters: { range: "past-30-days", stateTypes: ["FAILED"] },
	};
	withStoredFilters("mine", [mine], () => {
		expect(defaultFilterSearch({})).toMatchObject({
			range: "past-30-days",
			"state-types": ["FAILED"],
		});
	});
	withStoredFilters("deleted", [mine], () => {
		expect(defaultFilterSearch({})).toMatchObject({ range: "past-7-days" });
	});
});

it("leaves a runs URL that already filters the page", () => {
	expect(defaultFilterSearch({ tags: "nightly" })).toBeUndefined();
	expect(
		defaultFilterSearch({ start: "2026-11-01T00:00:00Z" }),
	).toBeUndefined();
});
