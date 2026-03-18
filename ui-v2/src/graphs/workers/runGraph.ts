import type {
	HorizontalPositionSettings,
	VerticalPositionSettings,
} from "@/graphs/factories/position";
import type { NodesLayoutResponse, NodeWidths } from "@/graphs/models/layout";
import type { RunGraphData } from "@/graphs/models/RunGraph";

// eslint-disable-next-line import/default
import RunGraphWorker from "@/graphs/workers/runGraph.worker?worker&inline";

export type ClientMessage = ClientLayoutMessage;
export type WorkerMessage = WorkerLayoutMessage;

export type ClientLayoutMessage = {
	type: "layout";
	data: RunGraphData;
	widths: NodeWidths;
	horizontalSettings: HorizontalPositionSettings;
	verticalSettings: VerticalPositionSettings;
};

export type WorkerLayoutMessage = {
	type: "layout";
	layout: NodesLayoutResponse;
};

export interface IRunGraphWorker
	extends Omit<Worker, "postMessage" | "onmessage"> {
	postMessage: (command: ClientMessage, transfer?: Transferable[]) => void;
	onmessage:
		| ((this: Worker, event: MessageEvent<WorkerMessage>) => void)
		| null;
}

export function layoutWorkerFactory(
	onmessage: IRunGraphWorker["onmessage"],
): IRunGraphWorker {
	const worker = new RunGraphWorker() as IRunGraphWorker;

	worker.onmessage = onmessage;

	return worker;
}
