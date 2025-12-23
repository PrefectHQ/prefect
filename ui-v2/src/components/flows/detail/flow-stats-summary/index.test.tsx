import { describe, expect, it } from "vitest";
import { FlowStatsSummary } from "./index";
import {
	buildCompletedTaskRunsCountFilter,
	buildFailedTaskRunsCountFilter,
	buildFlowRunsCountFilterForHistory,
	buildFlowRunsHistoryFilter,
	buildRunningTaskRunsCountFilter,
	buildTaskRunsHistoryFilterForFlow,
	buildTotalTaskRunsCountFilter,
} from "./query-filters";

describe("FlowStatsSummary", () => {
	it("exports the FlowStatsSummary component", () => {
		expect(FlowStatsSummary).toBeDefined();
	});

	describe("query filter builders", () => {
		const flowId = "test-flow-id";

		it("buildFlowRunsHistoryFilter creates correct filter", () => {
			const filter = buildFlowRunsHistoryFilter(flowId, 60);
			expect(filter).toEqual({
				flows: { operator: "and_", id: { any_: [flowId] } },
				flow_runs: {
					operator: "and_",
					start_time: { is_null_: false },
				},
				offset: 0,
				limit: 60,
				sort: "START_TIME_DESC",
			});
		});

		it("buildFlowRunsCountFilterForHistory creates correct filter", () => {
			const filter = buildFlowRunsCountFilterForHistory(flowId);
			expect(filter).toEqual({
				flows: { operator: "and_", id: { any_: [flowId] } },
				flow_runs: {
					operator: "and_",
					start_time: { is_null_: false },
				},
			});
		});

		it("buildTotalTaskRunsCountFilter creates correct filter", () => {
			const filter = buildTotalTaskRunsCountFilter(flowId);
			expect(filter.flows).toBeDefined();
			expect(filter.flows?.id?.any_).toEqual([flowId]);
			expect(filter.task_runs?.state?.type?.any_).toEqual([
				"COMPLETED",
				"FAILED",
				"CRASHED",
				"RUNNING",
			]);
		});

		it("buildCompletedTaskRunsCountFilter creates correct filter", () => {
			const filter = buildCompletedTaskRunsCountFilter(flowId);
			expect(filter.flows).toBeDefined();
			expect(filter.task_runs?.state?.type?.any_).toEqual(["COMPLETED"]);
		});

		it("buildFailedTaskRunsCountFilter creates correct filter", () => {
			const filter = buildFailedTaskRunsCountFilter(flowId);
			expect(filter.flows).toBeDefined();
			expect(filter.task_runs?.state?.type?.any_).toEqual([
				"FAILED",
				"CRASHED",
			]);
		});

		it("buildRunningTaskRunsCountFilter creates correct filter", () => {
			const filter = buildRunningTaskRunsCountFilter(flowId);
			expect(filter.flows).toBeDefined();
			expect(filter.task_runs?.state?.type?.any_).toEqual(["RUNNING"]);
		});

		it("buildTaskRunsHistoryFilterForFlow creates correct filter", () => {
			const filter = buildTaskRunsHistoryFilterForFlow(flowId);
			expect(filter.flows).toBeDefined();
			expect(filter.flows?.id?.any_).toEqual([flowId]);
			expect(filter.history_interval_seconds).toBeDefined();
		});
	});
});
