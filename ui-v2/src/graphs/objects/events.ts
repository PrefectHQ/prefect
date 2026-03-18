import type { Cull } from "@pixi-essentials/cull";
import type { Application, Container } from "pixi.js";
import type { Viewport } from "pixi-viewport";
import { eventsFactory } from "@/graphs/factories/events";
import type { HorizontalScale } from "@/graphs/factories/position";
import type { RunGraphEvent } from "@/graphs/models";
import type { LayoutSettings } from "@/graphs/models/layout";
import type {
	RequiredGraphConfig,
	RunGraphData,
	RunGraphStyles,
} from "@/graphs/models/RunGraph";
import type { GraphItemSelection } from "@/graphs/models/selection";
import type { ViewportDateRange } from "@/graphs/models/viewport";
import type { FontFactory } from "@/graphs/objects/fonts";
import type { VisibilityCull } from "@/graphs/services/visibilityCull";

type Events = {
	scaleCreated: HorizontalScale;
	scaleUpdated: HorizontalScale;
	applicationCreated: Application;
	applicationResized: Application;
	stageCreated: HTMLDivElement;
	stageUpdated: HTMLDivElement;
	viewportCreated: Viewport;
	viewportDateRangeUpdated: ViewportDateRange;
	viewportMoved: null;
	configCreated: RequiredGraphConfig;
	configUpdated: RequiredGraphConfig;
	fontLoaded: FontFactory;
	containerCreated: Container;
	layoutSettingsUpdated: LayoutSettings;
	layoutSettingsCreated: LayoutSettings;
	cullCreated: Cull;
	labelCullCreated: VisibilityCull;
	iconCullCreated: VisibilityCull;
	edgeCullCreated: VisibilityCull;
	runDataCreated: RunGraphData;
	runDataUpdated: RunGraphData;
	eventDataCreated: RunGraphEvent[];
	eventDataUpdated: RunGraphEvent[];
	itemSelected: GraphItemSelection | null;
	layoutUpdated: void;
	toggleCullCreated: VisibilityCull;
	stylesCreated: Required<RunGraphStyles>;
	stylesUpdated: Required<RunGraphStyles>;
};

export type EventKey = keyof Events;

export const emitter = eventsFactory<Events>();

export function waitForEvent<T extends EventKey>(event: T): Promise<Events[T]> {
	// making ts happy with this is just not worth it IMO since this is
	// only necessary for the emitter.off
	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	let handler: any;

	return new Promise<Events[T]>((resolve) => {
		handler = resolve;
		emitter.on(event, handler);
	}).then((value) => {
		emitter.off(event, handler);

		return value;
	});
}
