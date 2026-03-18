import type { RunGraphNodes } from "@/graphs/models/RunGraph";

export function getEdgesCount(nodes: RunGraphNodes): number {
	let numberOfEdges = 0;

	for (const [, { children }] of nodes) {
		numberOfEdges += children.length;
	}

	return numberOfEdges;
}
