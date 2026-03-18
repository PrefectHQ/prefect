import throttle from "lodash.throttle";
import { Container } from "pixi.js";
import { DEFAULT_ROOT_COLLISION_THROTTLE } from "@/graphs/consts";
import type { EventFactory } from "@/graphs/factories/event";
import type { EventClusterFactory } from "@/graphs/factories/eventCluster";
import { flowRunEventFactory } from "@/graphs/factories/flowRunEvent";
import { nodeFlowRunEventFactory } from "@/graphs/factories/nodeFlowRunEvent";
import type { RunGraphEvent } from "@/graphs/models";
import { emitter } from "@/graphs/objects/events";
import { layout, waitForSettings } from "@/graphs/objects/settings";
import { clusterHorizontalCollisions } from "@/graphs/utilities/detectHorizontalCollisions";

type RunEventsFactoryProps = {
	isRoot?: boolean;
	parentStartDate?: Date;
};

// eslint-disable-next-line @typescript-eslint/explicit-function-return-type
export async function runEventsFactory({
	isRoot,
	parentStartDate,
}: RunEventsFactoryProps = {}) {
	const settings = await waitForSettings();

	const events = new Map<string, EventFactory>();
	const eventsCreationPromises = new Map<string, Promise<void>>();
	const clusterNodes: EventClusterFactory[] = [];
	let availableClusterNodes: EventClusterFactory[] = [];

	const container = new Container();
	let internalData: RunGraphEvent[] | null = null;

	emitter.on("scaleUpdated", () => update());

	async function render(newData?: RunGraphEvent[]): Promise<void> {
		if (newData) {
			internalData = newData;
		}

		if (!internalData) {
			return;
		}

		const promises: Promise<void>[] = [];

		for (const artifact of internalData) {
			promises.push(createEvent(artifact));
		}

		await Promise.all(promises);

		update();
	}

	async function createEvent(event: RunGraphEvent): Promise<void> {
		if (events.has(event.id)) {
			return events.get(event.id)!.render();
		}

		if (eventsCreationPromises.has(event.id)) {
			return await eventsCreationPromises.get(event.id);
		}

		const eventCreationPromise = (async () => {
			const factory = isRoot
				? await flowRunEventFactory({ type: "event", event })
				: await nodeFlowRunEventFactory({
						type: "event",
						event,
						parentStartDate,
					});

			events.set(event.id, factory);

			container!.addChild(factory.element);
		})();

		eventsCreationPromises.set(event.id, eventCreationPromise);

		await eventCreationPromise;

		eventsCreationPromises.delete(event.id);

		return events.get(event.id)!.render();
	}

	function update(): void {
		if (settings.disableEvents || !layout.isTemporal()) {
			return;
		}

		checkLayout();
	}

	const checkLayout = throttle(async () => {
		availableClusterNodes = [...clusterNodes];

		await clusterHorizontalCollisions({
			items: events,
			createCluster,
		});

		for (const cluster of availableClusterNodes) {
			cluster.render();
		}
	}, DEFAULT_ROOT_COLLISION_THROTTLE);

	async function createCluster(): Promise<EventClusterFactory> {
		if (availableClusterNodes.length > 0) {
			return availableClusterNodes.pop()!;
		}

		const newCluster = isRoot
			? await flowRunEventFactory({ type: "cluster" })
			: await nodeFlowRunEventFactory({ type: "cluster", parentStartDate });

		container!.addChild(newCluster.element);
		clusterNodes.push(newCluster);

		return newCluster;
	}

	return {
		element: container,
		render,
		update,
	};
}
