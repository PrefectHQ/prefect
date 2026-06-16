import { describe, expect, it } from "vitest";
import type { RunGraphNode } from "@/graphs/models/RunGraph";
import { getNodeBarWidth } from "./nodeBar";

const startTime = new Date("2024-01-01T00:00:00.000Z");
const now = new Date("2024-01-01T00:00:10.000Z");
const borderRadius = 6;
const columnSize = 10;

function createNode(overrides: Partial<RunGraphNode> = {}): RunGraphNode {
	return {
		kind: "task-run",
		id: "task-run-id",
		label: "task",
		state_type: "COMPLETED",
		start_time: startTime,
		end_time: new Date("2024-01-01T00:00:02.000Z"),
		parents: [],
		children: [],
		artifacts: [],
		...overrides,
	};
}

describe("getNodeBarWidth", () => {
	it("uses the minimum width for pending task runs without an end time", () => {
		const width = getNodeBarWidth(
			createNode({
				state_type: "PENDING",
				end_time: null,
			}),
			borderRadius,
			columnSize,
			true,
			now,
		);

		expect(width).toBe(borderRadius * 2);
	});

	it("uses now for running task runs without an end time", () => {
		const width = getNodeBarWidth(
			createNode({
				state_type: "RUNNING",
				end_time: null,
			}),
			borderRadius,
			columnSize,
			true,
			now,
		);

		expect(width).toBe(100);
	});

	it("uses now for pending flow runs without an end time", () => {
		const width = getNodeBarWidth(
			createNode({
				kind: "flow-run",
				state_type: "PENDING",
				end_time: null,
			}),
			borderRadius,
			columnSize,
			true,
			now,
		);

		expect(width).toBe(100);
	});

	it("uses the completed duration for terminal task runs", () => {
		const width = getNodeBarWidth(
			createNode(),
			borderRadius,
			columnSize,
			true,
			now,
		);

		expect(width).toBe(20);
	});

	it("uses a full column outside duration layouts", () => {
		const width = getNodeBarWidth(
			createNode({
				state_type: "PENDING",
				end_time: null,
			}),
			borderRadius,
			columnSize,
			false,
			now,
		);

		expect(width).toBe(columnSize);
	});
});
