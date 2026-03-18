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
import { waitForApplication, waitForViewport } from "@/graphs/objects";
import { emitter } from "@/graphs/objects/events";
import { waitForScale } from "@/graphs/objects/scale";
import { selectItem } from "@/graphs/objects/selection";
import { layout, waitForSettings } from "@/graphs/objects/settings";
import { waitForStyles } from "@/graphs/objects/styles";
import { itemIsClusterFactory } from "@/graphs/utilities/detectHorizontalCollisions";

export type FlowRunEventFactory = Awaited<
	ReturnType<typeof flowRunEventFactory>
>;

type EventFactoryOptions =
	| { type: "event"; event: RunGraphEvent }
	| { type: "cluster" };

type EventFactoryType<T> = T extends { type: "event" }
	? EventFactory
	: T extends { type: "cluster" }
		? EventClusterFactory
		: never;

type RenderPropsType<T> = T extends { type: "cluster" }
	? EventClusterFactoryRenderProps
	: undefined;

export async function flowRunEventFactory<T extends EventFactoryOptions>(
	options: T,
): Promise<EventFactoryType<T>> {
	const application = await waitForApplication();
	const viewport = await waitForViewport();
	const styles = await waitForStyles();
	const settings = await waitForSettings();
	let scale = await waitForScale();

	const factory = (await getFactory()) as EventFactoryType<T>;

	factory.element.on("click", (clickEvent) => {
		clickEvent.stopPropagation();

		const { element } = factory;

		const position = {
			x: element.position.x,
			y: element.position.y,
			width: element.width,
			height: element.height,
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
	emitter.on("viewportMoved", () => updatePosition());

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

		if (!date || settings.disableEvents || !layout.isTemporal()) {
			return;
		}

		const { element } = factory;

		const x = scale(date) * viewport.scale._x + viewport.worldTransform.tx;
		const centeredX = x - element.width / 2;
		const y =
			application.screen.height - element.height - styles.eventBottomMargin;

		element.position.set(centeredX, y);
	}

	return {
		...factory,
		render,
	};
}
