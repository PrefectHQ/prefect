import { DEFAULT_ROOT_EVENT_Z_INDEX } from "@/graphs/consts";
import { eventDataFactory } from "@/graphs/factories/eventData";
import { runEventsFactory } from "@/graphs/factories/runEvents";
import type { RunGraphEvent } from "@/graphs/models";
import { waitForApplication } from "@/graphs/objects/application";
import { waitForConfig } from "@/graphs/objects/config";
import { type EventKey, emitter, waitForEvent } from "@/graphs/objects/events";
import { waitForRunData } from "@/graphs/objects/nodes";
import { layout, waitForSettings } from "@/graphs/objects/settings";

let stopEventData: (() => void) | null = null;
let rootGraphEvents: RunGraphEvent[] | null = null;

export async function startFlowRunEvents(): Promise<void> {
	const application = await waitForApplication();
	const config = await waitForConfig();
	const settings = await waitForSettings();
	const data = await waitForRunData();

	const {
		element,
		render: renderEvents,
		update,
	} = await runEventsFactory({ isRoot: true });

	element.zIndex = DEFAULT_ROOT_EVENT_Z_INDEX;

	async function render(data?: RunGraphEvent[]): Promise<void> {
		if (!layout.isTemporal() || settings.disableEvents) {
			application.stage.removeChild(element);
			return;
		}

		application.stage.addChild(element);

		await renderEvents(data);
	}

	const response = await eventDataFactory(
		() => ({
			nodeId: config.runId,
			since: data.start_time,
			until: data.end_time ?? new Date(),
		}),
		(data) => {
			const event: EventKey = rootGraphEvents
				? "eventDataUpdated"
				: "eventDataCreated";

			rootGraphEvents = data;

			emitter.emit(event, rootGraphEvents);

			render(data);
		},
	);

	emitter.on("configUpdated", () => render());
	emitter.on("viewportMoved", () => update());
	emitter.on("layoutSettingsUpdated", () => render());

	stopEventData = response.stop;

	response.start();
}

export function stopFlowRunEvents(): void {
	stopEventData?.();
	stopEventData = null;
	rootGraphEvents = null;
}

export async function waitForRunEvents(): Promise<RunGraphEvent[] | null> {
	if (rootGraphEvents) {
		return rootGraphEvents;
	}

	return await waitForEvent("eventDataCreated");
}
