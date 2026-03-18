import type { NodesLayoutResponse } from "@/graphs/models/layout";
import { exhaustive } from "@/graphs/utilities/exhaustive";
import { getHorizontalLayout } from "@/graphs/workers/layouts/horizontal";
import { getVerticalLayout } from "@/graphs/workers/layouts/vertical";
import type {
	ClientLayoutMessage,
	ClientMessage,
	WorkerMessage,
} from "@/graphs/workers/runGraph";

onmessage = onMessageHandler;

function onMessageHandler({ data }: MessageEvent<ClientMessage>): void {
	const { type } = data;

	switch (type) {
		case "layout":
			handleLayoutMessage(data);
			return;
		default:
			exhaustive(type);
	}
}

function post(message: WorkerMessage): void {
	postMessage(message);
}

async function handleLayoutMessage(
	message: ClientLayoutMessage,
): Promise<void> {
	const { data } = message;
	const horizontalLayout = getHorizontalLayout(message);
	const verticalLayout = await getVerticalLayout(message, horizontalLayout);
	const positions: NodesLayoutResponse["positions"] = new Map();

	let maxRow = 0;
	let maxColumn = 0;

	for (const [nodeId, node] of data.nodes) {
		const horizontal = horizontalLayout.get(nodeId);
		const vertical = verticalLayout.get(nodeId);

		if (horizontal === undefined) {
			console.warn(
				`NodeId not found in horizontal layout: Skipping ${node.label}`,
			);
			continue;
		}

		if (vertical === undefined) {
			console.warn(
				`NodeId not found in vertical layout: Skipping ${node.label}`,
			);
			continue;
		}

		maxRow = Math.max(maxRow, vertical);
		maxColumn = Math.max(maxColumn, horizontal.column);

		positions.set(nodeId, {
			...horizontal,
			y: vertical,
			row: vertical,
		});
	}

	post({
		type: "layout",
		layout: {
			maxRow,
			maxColumn,
			positions,
		},
	});
}
