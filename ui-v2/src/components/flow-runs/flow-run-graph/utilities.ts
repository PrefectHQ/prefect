import type { RunGraphData, RunGraphEdge, RunGraphNode } from "@/graphs";

export function isEventTargetInput(target: EventTarget | null): boolean {
	if (!target || !(target instanceof HTMLElement)) {
		return false;
	}
	return ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName);
}

export function getFlowRunAttemptRunCounts(data: RunGraphData): number[] {
	const runCounts = new Set<number>();

	for (const node of data.nodes.values()) {
		for (const runCount of getEffectiveFlowRunRunCounts(node, data.nodes)) {
			runCounts.add(runCount);
		}
	}

	return Array.from(runCounts).sort((a, b) => a - b);
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
		if (nodeMatchesFlowRunAttempt(node, data.nodes, runCount)) {
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
	const graphEndTime = data.end_time === null ? null : endTime;

	return {
		...data,
		root_node_ids: rootNodeIds,
		start_time: startTime,
		end_time: graphEndTime,
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
	return edges.filter((edge) => {
		const node = nodes.get(edge.id);

		return node ? nodeMatchesFlowRunAttempt(node, nodes, runCount) : false;
	});
}

function nodeMatchesFlowRunAttempt(
	node: RunGraphNode,
	nodes: RunGraphData["nodes"],
	runCount: number,
): boolean {
	return getEffectiveFlowRunRunCounts(node, nodes).has(runCount);
}

function getEffectiveFlowRunRunCounts(
	node: RunGraphNode,
	nodes: RunGraphData["nodes"],
): Set<number> {
	if (node.flow_run_run_count !== 0 || shouldKeepRunCountZero(node)) {
		return new Set([node.flow_run_run_count]);
	}

	return getConnectedNonZeroRunCounts(node, nodes);
}

function shouldKeepRunCountZero(node: RunGraphNode): boolean {
	return node.kind === "flow-run" || node.state_type === "RUNNING";
}

function getConnectedNonZeroRunCounts(
	node: RunGraphNode,
	nodes: RunGraphData["nodes"],
): Set<number> {
	const runCounts = new Set<number>();
	const visited = new Set<string>([node.id]);
	const queue = [...node.parents, ...node.children].map((edge) => edge.id);

	for (const nodeId of queue) {
		if (visited.has(nodeId)) {
			continue;
		}

		visited.add(nodeId);

		const connectedNode = nodes.get(nodeId);

		if (!connectedNode) {
			continue;
		}

		if (connectedNode.flow_run_run_count === 0) {
			queue.push(
				...connectedNode.parents.map((edge) => edge.id),
				...connectedNode.children.map((edge) => edge.id),
			);
			continue;
		}

		runCounts.add(connectedNode.flow_run_run_count);
	}

	return runCounts.size > 0 ? runCounts : new Set([node.flow_run_run_count]);
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
