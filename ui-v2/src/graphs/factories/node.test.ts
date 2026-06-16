import { describe, expect, it } from "vitest";
import type { RunGraphNode } from "@/graphs/models/RunGraph";
import { getNodeCacheEndTime, shouldNodeTick } from "./node";

const startTime = new Date("2024-01-01T00:00:00.000Z");
const endTime = new Date("2024-01-01T00:00:02.000Z");
const now = new Date("2024-01-01T00:00:10.000Z");

function createNode(overrides: Partial<RunGraphNode> = {}): RunGraphNode {
	return {
		kind: "task-run",
		id: "task-run-id",
		label: "task",
		state_type: "COMPLETED",
		start_time: startTime,
		end_time: endTime,
		parents: [],
		children: [],
		artifacts: [],
		...overrides,
	};
}

describe("shouldNodeTick", () => {
	it("does not tick pending task placeholders", () => {
		expect(
			shouldNodeTick(
				createNode({
					state_type: "PENDING",
					end_time: null,
				}),
			),
		).toBe(false);
	});

	it("ticks running task runs without an end time", () => {
		expect(
			shouldNodeTick(
				createNode({
					state_type: "RUNNING",
					end_time: null,
				}),
			),
		).toBe(true);
	});

	it("ticks pending flow runs without an end time", () => {
		expect(
			shouldNodeTick(
				createNode({
					kind: "flow-run",
					state_type: "PENDING",
					end_time: null,
				}),
			),
		).toBe(true);
	});

	it("does not tick terminal task runs", () => {
		expect(shouldNodeTick(createNode())).toBe(false);
	});
});

describe("getNodeCacheEndTime", () => {
	it("uses a stable cache value for pending task placeholders", () => {
		const node = createNode({
			state_type: "PENDING",
			end_time: null,
		});

		expect(getNodeCacheEndTime(node, now)).toBe("pending-placeholder");
		expect(getNodeCacheEndTime(node, new Date("2024-01-01T00:01:00.000Z"))).toBe(
			"pending-placeholder",
		);
	});

	it("uses now for running task runs without an end time", () => {
		const node = createNode({
			state_type: "RUNNING",
			end_time: null,
		});

		expect(getNodeCacheEndTime(node, now)).toBe(now.getTime());
	});

	it("uses the end time for terminal task runs", () => {
		expect(getNodeCacheEndTime(createNode(), now)).toBe(endTime.getTime());
	});
});
