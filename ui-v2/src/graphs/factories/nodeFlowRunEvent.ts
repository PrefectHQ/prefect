import { type EventFactory, eventFactory } from "@/graphs/factories/event";
import {
	type EventClusterFactory,
	type EventClusterFactoryRenderProps,
	eventClusterFactory,
} from "@/graphs/factories/eventCluster";
import type {
	EventSelection,
	EventsSelection,
	RunGraphEvent,
} from "@/graphs/models";
import { waitForViewport } from "@/graphs/objects";
import { emitter } from "@/graphs/objects/events";
import { waitForScale } from "@/graphs/objects/scale";
import { selectItem } from "@/graphs/objects/selection";
import { layout, waitForSettings } from "@/graphs/objects/settings";
import { itemIsClusterFactory } from "@/graphs/utilities/detectHorizontalCollisions";

export type NodeFlowRunEventFactory = Awaited<
	ReturnType<typeof nodeFlowRunEventFactory>
>;

type NodeEventFactorySharedOptions = {
	parentStartDate?: Date;
};

type NodeEventFactoryOptions = NodeEventFactorySharedOptions &
	({ type: "event"; event: RunGraphEvent } | { type: "cluster" });

type EventFactoryType<T> = T extends { type: "event" }
	? EventFactory
	: T extends { type: "cluster" }
		? EventClusterFactory
		: never;

type RenderPropsType<T> = T extends { type: "cluster" }
	? EventClusterFactoryRenderProps
	: undefined;

export async function nodeFlowRunEventFactory<
	T extends NodeEventFactoryOptions,
>(options: T): Promise<EventFactoryType<T>> {
	const viewport = await waitForViewport();
	const settings = await waitForSettings();
	let scale = await waitForScale();

	const factory = (await getFactory()) as EventFactoryType<T>;

	factory.element.on("click", (clickEvent) => {
		clickEvent.stopPropagation();

		const { element } = factory;

		const globalPosition = element.getGlobalPosition();

		const position = {
			x: globalPosition.x,
			y: globalPosition.y,
			width: element.width * viewport.scale.x,
			height: element.height * viewport.scale.y,
		};

		const selectSettings: EventSelection | EventsSelection =
			itemIsClusterFactory(factory)
				? {
						kind: "events",
						ids: factory.getIds(),
						occurred: factory.getDate(),
						position,
					}
				: {
						kind: "event",
						id: factory.getId(),
						occurred: factory.getDate(),
						position,
					};

		selectItem(selectSettings);
	});

	emitter.on("scaleUpdated", (updated) => {
		scale = updated;
		updatePosition();
	});

	async function render(props?: RenderPropsType<T>): Promise<void> {
		await factory.render(props);
		updatePosition();
	}

	async function getFactory(): Promise<EventFactory | EventClusterFactory> {
		if (options.type === "event") {
			return await eventFactory(options.event);
		}

		return await eventClusterFactory();
	}

	function updatePosition(): void {
		const date = factory.getDate();
		const { parentStartDate } = options;

		if (
			!date ||
			settings.disableEvents ||
			!layout.isTemporal() ||
			!parentStartDate
		) {
			return;
		}

		const { element } = factory;

		const x = scale(date) - scale(parentStartDate);
		const centeredX = x - element.width / 2;
		const y = -element.height;

		element.position.set(centeredX, y);
	}

	return {
		...factory,
		render,
	};
}
