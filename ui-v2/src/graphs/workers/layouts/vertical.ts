import type { HorizontalLayout } from "@/graphs/workers/layouts/horizontal";
import { getVerticalNearestParentLayout } from "@/graphs/workers/layouts/nearestParentVertical";
import type { ClientLayoutMessage } from "@/graphs/workers/runGraph";

export type VerticalLayout = Map<string, number>;

export async function getVerticalLayout(
	message: ClientLayoutMessage,
	horizontal: HorizontalLayout,
): Promise<VerticalLayout> {
	if (message.verticalSettings.mode === "nearest-parent") {
		return await getVerticalNearestParentLayout(message, horizontal);
	}

	if (message.verticalSettings.mode === "duration-sorted") {
		return getVerticalDurationSortedLayout(message);
	}

	return getVerticalWaterfallLayout(message);
}

function getVerticalWaterfallLayout(
	message: ClientLayoutMessage,
): VerticalLayout {
	const layout: VerticalLayout = new Map();

	let index = 0;

	for (const [nodeId] of message.data.nodes) {
		layout.set(nodeId, index++);
	}

	return layout;
}

function getVerticalDurationSortedLayout(
	message: ClientLayoutMessage,
): VerticalLayout {
	const layout: VerticalLayout = new Map();

	const nodes = [...message.data.nodes.values()].sort((nodeA, nodeB) => {
		const aDuration =
			(nodeA.end_time ? nodeA.end_time.getTime() : new Date().getTime()) -
			nodeA.start_time.getTime();
		const bDuration =
			(nodeB.end_time ? nodeB.end_time.getTime() : new Date().getTime()) -
			nodeB.start_time.getTime();

		return bDuration - aDuration;
	});

	let index = 0;

	for (const node of nodes) {
		layout.set(node.id, index++);
	}

	return layout;
}
