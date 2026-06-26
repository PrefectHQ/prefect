import { describe, expect, it } from "vitest";
import type { RunGraphData, RunGraphNode } from "@/graphs";
import {
	filterRunGraphDataByFlowRunAttempt,
	getFlowRunAttemptRunCounts,
} from "./utilities";

const createNode = (
	id: string,
	flowRunRunCount: number,
	overrides: Partial<RunGraphNode> = {},
): RunGraphNode => ({
	kind: "task-run",
	id,
	label: id,
	state_type: "COMPLETED",
	flow_run_run_count: flowRunRunCount,
	start_time: new Date(`2024-01-0${flowRunRunCount + 1}T00:00:00.000Z`),
	end_time: new Date(`2024-01-0${flowRunRunCount + 1}T00:01:00.000Z`),
	parents: [],
	children: [],
	artifacts: [],
	...overrides,
});

describe("getFlowRunAttemptRunCounts", () => {
	it("returns sorted unique flow run attempt counts", () => {
		const data = createGraphData([
			createNode("task-2", 2),
			createNode("task-1", 1),
			createNode("task-1b", 1),
		]);

		expect(getFlowRunAttemptRunCounts(data)).toEqual([1, 2]);
	});
});

describe("filterRunGraphDataByFlowRunAttempt", () => {
	it("returns the original data for all attempts", () => {
		const data = createGraphData([createNode("task-1", 1)]);

		expect(filterRunGraphDataByFlowRunAttempt(data, "all")).toBe(data);
	});

	it("uses a finite end time for pending task placeholders", () => {
		const failedTask = createNode("failed-task", 1, {
			state_type: "FAILED",
			start_time: new Date("2024-01-01T00:00:00.000Z"),
			end_time: new Date("2024-01-01T00:01:00.000Z"),
			children: [{ id: "pending-task" }],
		});

		const pendingTask = createNode("pending-task", 1, {
			state_type: "PENDING",
			start_time: new Date("2024-01-01T00:02:00.000Z"),
			end_time: null,
			parents: [{ id: "failed-task" }],
		});

		const data = createGraphData([failedTask, pendingTask]);

		const filtered = filterRunGraphDataByFlowRunAttempt(data, 1);

		expect(filtered.start_time).toEqual(failedTask.start_time);
		expect(filtered.end_time).toEqual(pendingTask.start_time);
	});

	it("filters nodes, edges, roots, states, and time range to the selected attempt", () => {
		const task1 = createNode("task-1", 1, {
			children: [{ id: "task-2" }, { id: "task-3" }],
		});
		const task2 = createNode("task-2", 1, {
			parents: [{ id: "task-1" }],
		});
		const task3 = createNode("task-3", 2, {
			parents: [{ id: "task-1" }],
			start_time: new Date("2024-01-10T00:00:00.000Z"),
			end_time: new Date("2024-01-10T00:01:00.000Z"),
		});
		const data = createGraphData([task1, task2, task3], {
			root_node_ids: ["task-1"],
			states: [
				{
					id: "state-before",
					name: "Retrying",
					type: "RUNNING",
					timestamp: new Date("2024-01-09T00:00:00.000Z"),
				},
				{
					id: "state-in-range",
					name: "Running",
					type: "RUNNING",
					timestamp: new Date("2024-01-10T00:00:30.000Z"),
				},
			],
		});

		const filtered = filterRunGraphDataByFlowRunAttempt(data, 2);

		expect(Array.from(filtered.nodes.keys())).toEqual(["task-3"]);
		expect(filtered.root_node_ids).toEqual(["task-3"]);
		expect(filtered.nodes.get("task-3")?.parents).toEqual([]);
		expect(filtered.start_time).toEqual(task3.start_time);
		expect(filtered.end_time).toEqual(task3.end_time);
		expect(filtered.states?.map((state) => state.id)).toEqual([
			"state-in-range",
		]);
	});
});

function createGraphData(
	nodes: RunGraphNode[],
	overrides: Partial<RunGraphData> = {},
): RunGraphData {
	return {
		root_node_ids: nodes
			.filter((node) => node.parents.length === 0)
			.map((node) => node.id),
		start_time: new Date("2024-01-01T00:00:00.000Z"),
		end_time: new Date("2024-01-10T00:01:00.000Z"),
		nodes: new Map(nodes.map((node) => [node.id, node])),
		states: [],
		...overrides,
	};
}
