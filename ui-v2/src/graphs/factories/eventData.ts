import type {
	RunGraphEvent,
	RunGraphFetchEventsContext,
} from "@/graphs/models";
import type { MaybeGetter } from "@/graphs/models/utilities";
import { waitForConfig } from "@/graphs/objects/config";
import { waitForRunData } from "@/graphs/objects/nodes";
import { toValue } from "@/graphs/utilities";

type EventDataCallback = (data: RunGraphEvent[]) => void;

// eslint-disable-next-line @typescript-eslint/explicit-function-return-type
export async function eventDataFactory(
	context: MaybeGetter<RunGraphFetchEventsContext>,
	callback: EventDataCallback,
) {
	const runGraphData = await waitForRunData();
	const config = await waitForConfig();

	let interval: ReturnType<typeof setInterval> | undefined;
	let data: RunGraphEvent[] | null = null;

	async function start(): Promise<void> {
		try {
			data = await config.fetchEvents(toValue(context));

			callback(data);
		} catch (error) {
			console.error(error);
		}

		if (!runGraphData.end_time) {
			interval = setTimeout(() => start(), config.fetchEventsInterval);
		}
	}

	// todo: need a global way of stopping this when the graph is stopped
	function stop(): void {
		clearTimeout(interval);
	}

	return {
		start,
		stop,
	};
}
