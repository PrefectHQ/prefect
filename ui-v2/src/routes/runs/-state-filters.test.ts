import { describe, expect, it } from "vitest";
import {
	buildHistoryFilter,
	buildPaginationBody,
	buildTaskRunsPaginationBody,
	searchParams,
} from "./index";

describe("runs state filtering", () => {
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
