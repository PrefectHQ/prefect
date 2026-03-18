import { horizontalScaleFactory } from "@/graphs/factories/position";
import { getColumns } from "@/graphs/utilities/columns";
import type { ClientLayoutMessage } from "@/graphs/workers/runGraph";

export type HorizontalLayout = Map<
	string,
	{
		x: number;
		column: number;
	}
>;

export function getHorizontalLayout(
	message: ClientLayoutMessage,
): HorizontalLayout {
	if (message.horizontalSettings.mode === "dependency") {
		return getHorizontalDependencyLayout(message);
	}

	if (message.horizontalSettings.mode === "left-aligned") {
		return getHorizontalLeftAlignedLayout(message);
	}

	return getHorizontalTimeLayout(message);
}

function getHorizontalDependencyLayout({
	data,
	horizontalSettings,
}: ClientLayoutMessage): HorizontalLayout {
	const columns = getColumns(data);
	const scale = horizontalScaleFactory(horizontalSettings);
	const layout: HorizontalLayout = new Map();

	for (const [nodeId] of data.nodes) {
		const column = columns.get(nodeId);

		if (column === undefined) {
			console.warn(`Node not found in columns: Skipping ${nodeId}`);
			continue;
		}

		layout.set(nodeId, {
			x: scale(column),
			column,
		});
	}

	return layout;
}

function getHorizontalTimeLayout({
	data,
	horizontalSettings,
}: ClientLayoutMessage): HorizontalLayout {
	const scale = horizontalScaleFactory(horizontalSettings);
	const layout: HorizontalLayout = new Map();

	for (const [nodeId, node] of data.nodes) {
		const value = scale(node.start_time);

		layout.set(nodeId, {
			column: value,
			x: value,
		});
	}

	return layout;
}

function getHorizontalLeftAlignedLayout({
	data,
	horizontalSettings,
}: ClientLayoutMessage): HorizontalLayout {
	const scale = horizontalScaleFactory(horizontalSettings);
	const layout: HorizontalLayout = new Map();

	for (const [nodeId] of data.nodes) {
		layout.set(nodeId, {
			column: 0,
			x: scale(data.start_time),
		});
	}

	return layout;
}
