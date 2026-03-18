import type { RunGraphData, RunGraphNodes } from "@/graphs/models/RunGraph";

/**
 * A `Map` object that maps each node ID to its column.
 */
export type NodeColumns = Map<string, number>;

/**
 * Calculates the column for each node in the run graph using a faster or slower algorithm.
 *
 * This function first tries to calculate the columns using the faster `getColumnsFaster` function. If an error occurs during the calculation, it falls back to the slower `getColumnsSlower` function. The function takes in a `RunGraphData` object containing the root node IDs and nodes in the run graph.
 *
 * @param runGraphData - A `RunGraphData` object containing the root node IDs and nodes in the run graph.
 * @returns A `Map` object that maps each node ID to its column.
 */
export function getColumns({
	root_node_ids,
	nodes,
}: RunGraphData): NodeColumns {
	try {
		return getColumnsFaster(root_node_ids, nodes);
	} catch (error) {
		console.error(error);
		return getColumnsSlower(root_node_ids, nodes);
	}
}

/**
 * Calculates the column for each node in the run graph using a faster algorithm.
 *
 * This function sets up the initial columns for the root nodes and then calls `getChildrenColumns` to process all the children.
 *
 * Performance: 200k operations per seconds processing 23 connected nodes
 * Performance: 54-58 operations per second processing 2,000 highly connected nodes.
 *
 * @param nodeIds - The IDs of the root nodes.
 * @param nodes - The nodes in the run graph.
 * @returns A `Map` object that maps each node ID to its column.
 */
function getColumnsFaster(
	nodeIds: string[],
	nodes: RunGraphNodes,
): NodeColumns {
	const columns: NodeColumns = new Map();
	const childrenNodeIds: string[] = [];

	for (const id of nodeIds) {
		columns.set(id, 0);
		const node = nodes.get(id)!;

		for (const { id: childId } of node.children) {
			childrenNodeIds.push(childId);
		}
	}

	return getChildrenColumns(childrenNodeIds, nodes, columns);
}

/**
 * Calculates the column for each child node of the given nodes.
 *
 * This function processes the children of each node in the `nodeIds` array and calculates their columns based on the columns of their parents.
 *
 * @param nodeIds - The IDs of the nodes whose children should be processed.
 * @param nodes - The nodes in the run graph.
 * @param columns - A `Map` object that maps each node ID to its column.
 * @returns A `Map` object that maps each node ID to its column.
 * @throws An error if a node ID in `nodeIds` is not found in `nodes`.
 */
function getChildrenColumns(
	nodeIds: string[],
	nodes: RunGraphNodes,
	columns: NodeColumns,
): NodeColumns {
	for (const nodeId of nodeIds) {
		if (columns.has(nodeId)) {
			continue;
		}

		const node = nodes.get(nodeId);

		if (!node) {
			throw new Error("Node id not found in nodes");
		}

		const parentColumns: number[] = [];

		for (const parent of node.parents) {
			const column = columns.get(parent.id);

			if (column !== undefined) {
				parentColumns.push(column);
				continue;
			}

			getChildrenColumns([parent.id], nodes, columns);

			const parentColumn = columns.get(parent.id);

			if (parentColumn === undefined) {
				throw new Error("Could not determine parent column");
			}

			parentColumns.push(parentColumn);
		}

		const maxParentColumn = Math.max(...parentColumns);

		columns.set(nodeId, maxParentColumn + 1);

		const childNodeIds = node.children.map(({ id }) => id);

		if (childNodeIds.length) {
			getChildrenColumns(childNodeIds, nodes, columns);
		}
	}

	return columns;
}

/**
 * Calculates the column for each child node of the given nodes.
 *
 * This function processes the children of each node in the `nodeIds` array and calculates their columns based on the columns of their parents.
 *
 * Performance: 45k operations per second processing 23 connected nodes
 * Performance: 23-25 operations per second processing 2,000 highly connected nodes
 *
 * @param nodeIds - The IDs of the nodes whose children should be processed.
 * @param nodes - The nodes in the run graph.
 * @param columns - A `Map` object that maps each node ID to its column.
 * @returns A `Map` object that maps each node ID to its column.
 * @throws An error if a node ID in `nodeIds` is not found in `nodes`.
 */
// eslint-disable-next-line max-params
function getColumnsSlower(
	nodeIds: string[],
	nodes: RunGraphNodes,
	currentColumn = 0,
	columns = new Map(),
): NodeColumns {
	for (const nodeId of nodeIds) {
		const nodeColumnAssignment = columns.get(nodeId);

		if (!nodeColumnAssignment || nodeColumnAssignment < currentColumn) {
			columns.set(nodeId, currentColumn);
		}

		const node = nodes.get(nodeId)!;

		for (const { id: childId } of node.children) {
			getColumnsSlower([childId], nodes, currentColumn + 1, columns);
		}
	}

	return columns;
}
