import { describe, expect, it } from "vitest";
import { STATE_NAME_TO_TYPE } from "@/api/flow-runs/constants";
import { filterValuesToUrlParams } from "@/components/runs/use-runs-saved-filters";
import {
	SYSTEM_DEFAULT_FILTER,
	SYSTEM_FILTER_HIDE_SCHEDULED_ID,
	SYSTEM_FILTERS,
} from "@/components/runs/use-saved-filters";
import {
	buildHistoryFilter,
	buildPaginationBody,
	buildTaskRunsPaginationBody,
	searchParams,
} from "./index";

describe("runs state filtering", () => {
	it("hides every scheduled type through the saved preset, URL, list, and chart", () => {
		const preset = SYSTEM_FILTERS.find(
			(filter) => filter.id === SYSTEM_FILTER_HIDE_SCHEDULED_ID,
		);
		if (!preset) throw new Error("Missing Hide scheduled runs preset");
		const params = searchParams.parse(filterValuesToUrlParams(preset.filters));
		const expected = {
			operator: "and_",
			type: {
				any_: [
					"COMPLETED",
					"RUNNING",
					"PENDING",
					"FAILED",
					"CANCELLED",
					"CANCELLING",
					"CRASHED",
					"PAUSED",
				],
			},
		};
		const filters = [
			buildPaginationBody(params).flow_runs?.state,
			buildHistoryFilter(params).flow_runs?.state,
			buildTaskRunsPaginationBody(params).task_runs?.state,
		];
		for (const filter of filters) {
			expect(filter).toEqual(expected);
			expect(filter?.name).toBeUndefined();
			// Cached and custom names are included by type, without a name allowlist.
			expect(filter?.type?.any_).toContain(STATE_NAME_TO_TYPE.Cached);
			expect(filter?.type?.any_).toContain("FAILED");
			for (const name of [
				"Scheduled",
				"Late",
				"Resuming",
				"AwaitingRetry",
				"AwaitingConcurrencySlot",
			] as const) {
				expect(filter?.type?.any_).not.toContain(STATE_NAME_TO_TYPE[name]);
			}
		}
		expect(params.range).toBe("past-7-days");
	});

	it("keeps the Past week default unrestricted by state", () => {
		const params = searchParams.parse(
			filterValuesToUrlParams(SYSTEM_DEFAULT_FILTER.filters),
		);
		expect(params.range).toBe("past-7-days");
		expect(buildPaginationBody(params).flow_runs?.state).toBeUndefined();
		expect(buildHistoryFilter(params).flow_runs?.state).toBeUndefined();
		expect(
			buildTaskRunsPaginationBody(params).task_runs?.state,
		).toBeUndefined();
	});

	it("preserves exact names in existing user-saved filters", () => {
		const params = searchParams.parse(
			filterValuesToUrlParams({ state: ["Completed", "Cached"] }),
		);
		expect(buildPaginationBody(params).flow_runs?.state).toEqual({
			operator: "and_",
			name: { any_: ["Completed", "Cached"] },
		});
	});

	it("uses the same exact type/name filter for the flow list and chart", () => {
		const params = searchParams.parse({
			state: ["Baseline, NOT Met"],
			"state-types": ["FAILED"],
		});
		const expected = {
			operator: "and_",
			name: { any_: ["Baseline, NOT Met"] },
			type: { any_: ["FAILED"] },
		};
		expect(buildPaginationBody(params).flow_runs?.state).toEqual(expected);
		expect(buildHistoryFilter(params).flow_runs?.state).toEqual(expected);
		const task = buildTaskRunsPaginationBody(params);
		expect(task.task_runs?.state).toEqual(expected);
		expect(task.flow_runs?.state).toBeUndefined();
	});
});
