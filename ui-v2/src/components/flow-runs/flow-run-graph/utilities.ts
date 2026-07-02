import type { RunGraphData, RunGraphEdge, RunGraphNode } from "@/graphs";

export function isEventTargetInput(target: EventTarget | null): boolean {
	if (!target || !(target instanceof HTMLElement)) {
		return false;
	}
	return ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName);
}

export function getFlowRunAttemptRunCounts(data: RunGraphData): number[] {
	return Array.from(
		new Set(Array.from(data.nodes.values(), (node) => node.flow_run_run_count)),
	).sort((a, b) => a - b);
}

export function filterRunGraphDataByFlowRunAttempt(
	data: RunGraphData,
	runCount: number | "all",
): RunGraphData {
	if (runCount === "all") {
		return data;
	}

	const nodes = new Map<string, RunGraphNode>();

	for (const [nodeId, node] of data.nodes) {
		if (node.flow_run_run_count === runCount) {
			nodes.set(nodeId, {
				...node,
				parents: filterEdges(node.parents, data.nodes, runCount),
				children: filterEdges(node.children, data.nodes, runCount),
			});
		}
	}

	if (nodes.size === 0) {
		return {
			...data,
			root_node_ids: [],
			nodes,
			states: [],
		};
	}

	const rootNodeIds = Array.from(nodes.values())
		.filter((node) => node.parents.length === 0)
		.map((node) => node.id);
	const { startTime, endTime } = getRunTimeRange(Array.from(nodes.values()));

	return {
		...data,
		root_node_ids: rootNodeIds,
		start_time: startTime,
		end_time: endTime,
		nodes,
		states: data.states?.filter((state) => {
			const timestamp = state.timestamp.getTime();
			const startsAfterRangeStart = timestamp >= startTime.getTime();
			const endsBeforeRangeEnd = !endTime || timestamp <= endTime.getTime();

			return startsAfterRangeStart && endsBeforeRangeEnd;
		}),
	};
}

function filterEdges(
	edges: RunGraphEdge[],
	nodes: RunGraphData["nodes"],
	runCount: number,
): RunGraphEdge[] {
	return edges.filter(
		(edge) => nodes.get(edge.id)?.flow_run_run_count === runCount,
	);
}

function getRunTimeRange(nodes: RunGraphNode[]): {
	startTime: Date;
	endTime: Date | null;
} {
	const startTime = minDate(nodes.map((node) => node.start_time));

	const hasActivelyRunningNode = nodes.some(
		(node) =>
			node.end_time === null &&
			(node.kind === "flow-run" || node.state_type === "RUNNING"),
	);

	if (hasActivelyRunningNode) {
		return { startTime, endTime: null };
	}

	return {
		startTime,
		endTime: maxDate(nodes.map((node) => node.end_time ?? node.start_time)),
	};
}

function minDate(dates: Date[]): Date {
	return new Date(Math.min(...dates.map((date) => date.getTime())));
}

function maxDate(dates: Date[]): Date {
	return new Date(Math.max(...dates.map((date) => date.getTime())));
}
