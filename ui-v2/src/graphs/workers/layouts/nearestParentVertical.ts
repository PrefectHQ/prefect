import type { RunGraphNode } from "@/graphs/models";
import type { HorizontalLayout } from "@/graphs/workers/layouts/horizontal";
import type { VerticalLayout } from "@/graphs/workers/layouts/vertical";
import type { ClientLayoutMessage } from "@/graphs/workers/runGraph";

type NodeShoveDirection = 1 | -1;

export async function getVerticalNearestParentLayout(
	message: ClientLayoutMessage,
	horizontal: HorizontalLayout,
): Promise<VerticalLayout> {
	const defaultNearestParentPosition = 0;
	const minimumNodeEdgeGap = 16;
	const nodeShoveRecords = new Map<string, NodeShoveDirection>();
	const rowTracker = new Map<number, Set<string>>();
	let lowestRow = 0;

	const layout: VerticalLayout = new Map();

	for await (const [nodeId] of message.data.nodes) {
		const node = message.data.nodes.get(nodeId);

		if (!node) {
			console.warn(
				"NearestParentLayout: Node was not found in the data",
				nodeId,
			);
			continue;
		}

		const row = await getNearestParentPosition(node);

		setLayoutNode(nodeId, row);
	}

	purgeNegativeLayoutPositions();

	return layout;

	async function getNearestParentPosition(node: RunGraphNode): Promise<number> {
		const { x: nodeStartX } = horizontal.get(node.id) ?? {};

		if (nodeStartX === undefined) {
			console.warn(
				"NearestParentLayout: Node was not found in the horizontal layout",
				node.id,
			);
			return defaultNearestParentPosition;
		}

		// if one dependency
		if (node.parents.length === 1) {
			if (layout.has(node.parents[0].id)) {
				return await placeNearUpstreamNode(node.parents[0].id, nodeStartX);
			}

			console.warn(
				"NearestParentLayout: Parent node not found in layout",
				node.parents[0].id,
			);
			return defaultNearestParentPosition;
		}

		// if more than one dependency – add to the middle of upstream dependencies
		if (node.parents.length > 0) {
			const upstreamRows = node.parents.map(({ id }) => {
				const row = layout.get(id);

				if (row === undefined) {
					console.warn(
						"NearestParentLayout: Parent node not found in layout",
						id,
					);
					return defaultNearestParentPosition;
				}

				return row;
			});

			const upstreamRowsSum = upstreamRows.reduce(
				(sum, position) => sum + position,
				0,
			);
			const upstreamRowsAverage = upstreamRowsSum / upstreamRows.length;
			const row = Math.round(upstreamRowsAverage);

			if (isPositionTaken(nodeStartX, row)) {
				const overlappingNodes = getOverlappingNodeIds(nodeStartX, row)!;

				const parentIds = node.parents.map(({ id }) => id);
				const overlappingParentNodes = overlappingNodes.filter((layoutId) => {
					return parentIds.includes(layoutId);
				});

				if (overlappingParentNodes.length > 0 || overlappingNodes.length > 1) {
					// upstream node parents always win, or if there are more than one node in the way
					const [upstreamLayoutItemId] =
						overlappingParentNodes.length > 0
							? overlappingParentNodes
							: overlappingNodes;

					const shoveDirection = getShoveDirectionWeightedByDependencies(
						upstreamRows,
						row,
						nodeShoveRecords.get(upstreamLayoutItemId),
					);

					nodeShoveRecords.set(upstreamLayoutItemId, shoveDirection);

					return await placeNearUpstreamNode(upstreamLayoutItemId, nodeStartX);
				}

				return await argueWithCompetingUpstreamPlacement({
					competingNodeId: overlappingNodes[0],
					upstreamRows,
					nodeStartX,
					desiredRow: row,
				});
			}
		}

		// if zero dependencies
		return placeRootNode(nodeStartX, defaultNearestParentPosition);
	}

	function placeRootNode(nodeStartX: number, defaultPosition: number): number {
		if (isPositionTaken(nodeStartX, defaultPosition)) {
			return placeRootNode(nodeStartX, defaultPosition + 1);
		}

		return defaultPosition;
	}

	async function placeNearUpstreamNode(
		upstreamNodeId: string,
		nodeStartX: number,
	): Promise<number> {
		// See this diagram for how shove logic works in this scenario
		// https://www.figma.com/file/1u1oXkiYRxgtqWSRG9Yely/DAG-Design?node-id=385%3A2782&t=yRLIggko0TzbMaIG-4
		const upstreamRow = layout.get(upstreamNodeId);

		if (upstreamRow === undefined) {
			console.warn(
				"NearestParentLayout: Upstream node not found in layout",
				upstreamNodeId,
			);
			return defaultNearestParentPosition;
		}

		if (!nodeShoveRecords.get(upstreamNodeId)) {
			nodeShoveRecords.set(upstreamNodeId, 1);
		}

		const nextDependencyShove = nodeShoveRecords.get(upstreamNodeId)!;

		if (isPositionTaken(nodeStartX, upstreamRow)) {
			if (
				nextDependencyShove === 1 &&
				!isPositionTaken(nodeStartX, upstreamRow + 1)
			) {
				nodeShoveRecords.set(upstreamNodeId, -1);
				return upstreamRow + 1;
			}
			if (!isPositionTaken(nodeStartX, upstreamRow - 1)) {
				nodeShoveRecords.set(upstreamNodeId, 1);
				return upstreamRow - 1;
			}

			await shove({
				direction: nextDependencyShove,
				nodeStartX,
				desiredRow: upstreamRow + nextDependencyShove,
			});

			nodeShoveRecords.set(upstreamNodeId, nextDependencyShove === 1 ? -1 : 1);

			return upstreamRow + nextDependencyShove;
		}
		return upstreamRow;
	}

	function isPositionTaken(nodeStartX: number, row: number): boolean {
		if (layout.size === 0) {
			return false;
		}

		let positionTaken = false;

		const rowNodes = rowTracker.get(row) ?? [];

		for (const nodeId of rowNodes) {
			const firstNodePosition = layout.get(nodeId)!;
			const firstNodeEndX = getNodeEndX(nodeId);

			const overlapping = isNodesOverlapping({
				firstNodeEndX,
				firstNodeRow: firstNodePosition,
				lastNodeStartX: nodeStartX,
				lastNodeRow: row,
			});

			if (overlapping) {
				positionTaken = true;
				break;
			}
		}

		return positionTaken;
	}

	type ShoveProps = {
		direction: NodeShoveDirection;
		nodeStartX: number;
		desiredRow: number;
	};
	async function shove({
		direction,
		nodeStartX,
		desiredRow,
	}: ShoveProps): Promise<void> {
		const overlappingNodeIds = getOverlappingNodeIds(nodeStartX, desiredRow);

		if (!overlappingNodeIds) {
			return;
		}

		for await (const nodeId of overlappingNodeIds) {
			// push nodes and recursively shove as needed
			const overlappingRow = layout.get(nodeId);
			const { x: nodeStartX } = horizontal.get(nodeId) ?? {};

			if (overlappingRow === undefined || nodeStartX === undefined) {
				console.warn(
					"NearestParentLayout - shove: Node was not found in the vertical or horizontal layout",
					nodeId,
				);
				continue;
			}

			const desiredRow = overlappingRow + direction;

			await shove({
				direction,
				nodeStartX,
				desiredRow,
			});

			setLayoutNode(nodeId, desiredRow);
		}
	}

	type IsNodesOverlappingProps = {
		firstNodeEndX: number;
		firstNodeRow: number;
		lastNodeStartX: number;
		lastNodeRow: number;
	};
	function isNodesOverlapping({
		firstNodeEndX,
		firstNodeRow,
		lastNodeStartX,
		lastNodeRow,
	}: IsNodesOverlappingProps): boolean {
		return (
			firstNodeRow === lastNodeRow &&
			firstNodeEndX + minimumNodeEdgeGap >= lastNodeStartX
		);
	}

	function getOverlappingNodeIds(
		nodeStartX: number,
		row: number,
	): string[] | undefined {
		const overlappingNodeIds: string[] = [];

		const rowNodes = rowTracker.get(row) ?? [];

		for (const nodeId of rowNodes) {
			const firstNodeEndX = getNodeEndX(nodeId);
			const firstNodeRow = layout.get(nodeId);

			if (firstNodeRow === undefined) {
				console.warn(
					"NearestParentLayout - getOverlappingNodeIds: Node was not found in the layout",
					nodeId,
				);
				continue;
			}

			const isItemOverlapping = isNodesOverlapping({
				firstNodeEndX,
				firstNodeRow,
				lastNodeStartX: nodeStartX,
				lastNodeRow: row,
			});

			if (isItemOverlapping) {
				overlappingNodeIds.push(nodeId);
			}
		}

		if (overlappingNodeIds.length === 0) {
			return;
		}

		// sort last to first
		overlappingNodeIds.sort((itemAId, itemBId) => {
			const itemAEndX = getNodeEndX(itemAId);
			const itemBEndX = getNodeEndX(itemBId);
			if (itemAEndX < itemBEndX) {
				return 1;
			}
			if (itemAEndX > itemBEndX) {
				return -1;
			}
			return 0;
		});

		return overlappingNodeIds;
	}

	function getShoveDirectionWeightedByDependencies(
		parentRows: number[],
		position: number,
		defaultGravity?: NodeShoveDirection,
	): NodeShoveDirection {
		// check if node has more connections above or below, prefer placement in that direction
		const upwardConnections = parentRows.filter((row) => row < position).length;
		const downwardConnections = parentRows.filter(
			(row) => row > position,
		).length;

		if (upwardConnections > downwardConnections) {
			return -1;
		}

		return defaultGravity ?? 1;
	}

	type ArgueWithCompetingUpstreamPlacementProps = {
		desiredRow: number;
		nodeStartX: number;
		upstreamRows: number[];
		competingNodeId: string;
	};
	async function argueWithCompetingUpstreamPlacement({
		desiredRow,
		nodeStartX,
		upstreamRows,
		competingNodeId,
	}: ArgueWithCompetingUpstreamPlacementProps): Promise<number> {
		const competitor = layout.get(competingNodeId);

		if (competitor === undefined) {
			console.warn(
				"NearestParentLayout - argueWithCompetingUpstreamPlacement: Competitor node was not found in the layout",
				competingNodeId,
			);
			return desiredRow;
		}

		const [competitorAboveConnections, competitorBelowConnections] =
			getNodeParentDirectionCounts(competingNodeId);
		const nodeAboveConnections = upstreamRows.filter(
			(upstreamPosition) => upstreamPosition < desiredRow,
		).length;
		const nodeBelowConnections = upstreamRows.filter(
			(upstreamPosition) => upstreamPosition > desiredRow,
		).length;

		if (nodeAboveConnections > nodeBelowConnections) {
			// node has more above
			if (
				competitorAboveConnections > competitorBelowConnections &&
				competitorAboveConnections > nodeAboveConnections
			) {
				// competitor has more above than below, and more above than node
				// node wins, shove competitor up
				await shove({
					direction: -1,
					nodeStartX,
					desiredRow,
				});
				return desiredRow;
			}
			if (competitorBelowConnections > competitorAboveConnections) {
				// competitor has more below than above
				// node wins, shove competitor down
				await shove({
					direction: 1,
					nodeStartX,
					desiredRow,
				});
				return desiredRow;
			}

			// competitor has equal above and below, or node has more above
			// place node above competitor
			nodeShoveRecords.set(competingNodeId, -1);
		}

		if (nodeBelowConnections > nodeAboveConnections) {
			// node has more below
			if (
				competitorBelowConnections > competitorAboveConnections &&
				competitorBelowConnections > nodeBelowConnections
			) {
				// competitor has more below than above, and more below than node
				// node wins, shove competitor down
				await shove({
					direction: 1,
					nodeStartX,
					desiredRow,
				});
				return desiredRow;
			}

			if (competitorAboveConnections > competitorBelowConnections) {
				// competitor has more above than below
				// node wins, shove competitor up
				await shove({
					direction: -1,
					nodeStartX,
					desiredRow,
				});
				return desiredRow;
			}

			// competitor has equal above and below, or node has more below
			// place node below competitor
			nodeShoveRecords.set(competingNodeId, 1);
		}

		return await placeNearUpstreamNode(competingNodeId, nodeStartX);
	}

	function getNodeParentDirectionCounts(
		nodeId: string,
	): [up: number, down: number] {
		const node = message.data.nodes.get(nodeId);
		const nodeRow = layout.get(nodeId);

		if (!node || nodeRow === undefined) {
			console.warn(
				"NearestParentLayout: Node was not found in either the data or layout",
				nodeId,
			);
			return [0, 0];
		}

		return node.parents.reduce(
			(counts, parent) => {
				const parentRow = layout.get(parent.id);

				if (parentRow === undefined) {
					console.warn(
						"NearestParentLayout - getNodeParentDirectionCounts: Parent node not found on layout data",
						nodeId,
					);
					return counts;
				}

				if (parentRow < nodeRow) {
					counts[0] += 1;
				}

				if (parentRow > nodeRow) {
					counts[1] += 1;
				}

				return counts;
			},
			[0, 0],
		);
	}

	function getNodeEndX(nodeId: string): number {
		const { x: nodeStartX } = horizontal.get(nodeId) ?? {};
		const nodeWidth = message.widths.get(nodeId);

		if (nodeStartX === undefined || nodeWidth === undefined) {
			console.warn(
				"NearestParentLayout: Node was not found in the horizontal layout and/or widths",
				nodeId,
			);
			return 0;
		}

		return nodeStartX + nodeWidth;
	}

	function setLayoutNode(nodeId: string, row: number): void {
		if (row < lowestRow) {
			lowestRow = row;
		}

		if (layout.has(nodeId)) {
			const previousRow = layout.get(nodeId)!;
			rowTracker.get(previousRow)?.delete(nodeId);
		}

		if (!rowTracker.has(row)) {
			rowTracker.set(row, new Set());
		}

		rowTracker.get(row)?.add(nodeId);

		layout.set(nodeId, row);
	}

	function purgeNegativeLayoutPositions(): void {
		if (lowestRow < 0) {
			for (const [nodeId] of layout) {
				const row = layout.get(nodeId)!;
				layout.set(nodeId, row + Math.abs(lowestRow));
			}
		}
	}
}
