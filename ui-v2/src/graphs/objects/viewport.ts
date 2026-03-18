import isEqual from "lodash.isequal";
import { Viewport } from "pixi-viewport";
import {
	DEFAULT_NODES_CONTAINER_NAME,
	DEFAULT_VIEWPORT_Z_INDEX,
} from "@/graphs/consts";
import type { ViewportDateRange } from "@/graphs/models/viewport";
import { waitForApplication } from "@/graphs/objects/application";
import { waitForConfig } from "@/graphs/objects/config";
import { cull, uncull } from "@/graphs/objects/culling";
import { emitter, waitForEvent } from "@/graphs/objects/events";
import { waitForRunData } from "@/graphs/objects/nodes";
import { waitForScale } from "@/graphs/objects/scale";
import { waitForSettings } from "@/graphs/objects/settings";
import { waitForStage } from "@/graphs/objects/stage";
import { waitForStyles } from "@/graphs/objects/styles";

let viewport: Viewport | null = null;
let viewportDateRange: ViewportDateRange | null = null;

export async function startViewport(): Promise<void> {
	const application = await waitForApplication();
	const stage = await waitForStage();

	// The events property type from pixi-viewport references @pixi/events
	// which conflicts with the bundled pixi.js v7 EventSystem type
	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	viewport = new Viewport({
		screenHeight: stage.clientHeight,
		screenWidth: stage.clientWidth,
		passiveWheel: false,
		events: application.renderer.events,
	} as any);

	// ensures the viewport is above the guides
	viewport.zIndex = DEFAULT_VIEWPORT_Z_INDEX;

	viewport
		.drag()
		.pinch()
		.wheel({
			trackpadPinch: true,
		})
		.decelerate({
			friction: 0.9,
		})
		.clampZoom({
			minWidth: stage.clientWidth / 2,
		});

	// Both the `moved` and `moved-end` events are required for a reliable `viewportMoved` event call that
	// includes the final positions for both scroll wheel and touch pad interactions.
	viewport
		.on("moved", () => {
			emitter.emit("viewportMoved", null);
		})
		.on("moved-end", () => {
			emitter.emit("viewportMoved", null);
		});

	application.stage.addChild(viewport);

	emitter.emit("viewportCreated", viewport);
	emitter.on("applicationResized", resizeViewport);
	emitter.on("scaleUpdated", () => updateViewportDateRange());

	startViewportDateRange();
}

export function stopViewport(): void {
	viewport = null;
	viewportDateRange = null;
}

type CenterViewportParameters = {
	animate?: boolean;
};

export async function centerViewport({
	animate,
}: CenterViewportParameters = {}): Promise<void> {
	const viewport = await waitForViewport();

	const container = viewport.getChildByName(DEFAULT_NODES_CONTAINER_NAME);

	if (!container) {
		throw new Error("Nodes container not found");
	}

	uncull();
	const { x, y, width, height } = container.getLocalBounds();

	// if the container doesn't have a size attempt to center to flow state
	if (!width || !height) {
		centerViewportOnStartAndEnd({ animate });

		return;
	}

	centerViewportOnNodes({ x, y, width, height, animate });
}

type CenterViewportOnNodesParameters = {
	x: number;
	y: number;
	width: number;
	height: number;
	animate?: boolean;
};

async function centerViewportOnNodes({
	x,
	y,
	width,
	height,
	animate,
}: CenterViewportOnNodesParameters): Promise<void> {
	const config = await waitForConfig();
	const styles = await waitForStyles();
	const viewport = await waitForViewport();

	const {
		guideTextSize,
		guideTextTopPadding,
		columnGap,
		rowGap,
		eventTargetSize,
	} = styles;

	const guidesOffset = guideTextSize + guideTextTopPadding;
	const widthWithGap = width + columnGap * 2;
	const heightWithGap = height + rowGap * 4 + guidesOffset + eventTargetSize;
	const scale = viewport.findFit(widthWithGap, heightWithGap);

	viewport.animate({
		position: {
			x: x + width / 2,
			y: y + height / 2 + guidesOffset,
		},
		scale: Math.min(scale, 1),
		time: animate ? config.animationDuration : 0,
		ease: "easeInOutQuad",
		removeOnInterrupt: true,
		callbackOnComplete: () => {
			cull();
			updateViewportDateRange();
		},
	});
}

async function centerViewportOnStartAndEnd({
	animate,
}: CenterViewportParameters): Promise<void> {
	const data = await waitForRunData();
	const config = await waitForConfig();
	const styles = await waitForStyles();
	const viewport = await waitForViewport();
	const graphScale = await waitForScale();

	let startX = graphScale(data.start_time) - styles.columnGap;
	let endX = graphScale(data.end_time ?? new Date()) + styles.columnGap;

	if (startX > endX) {
		const temp = startX;

		startX = endX;
		endX = temp;
	}

	const width = endX - startX;
	const x = startX + width / 2;
	const scale = viewport.findFit(width, 0);

	viewport.animate({
		position: {
			x,
			y: 0,
		},
		scale,
		time: animate ? config.animationDuration : 0,
		ease: "easeInOutQuad",
		removeOnInterrupt: true,
		callbackOnComplete: () => {
			cull();
			updateViewportDateRange();
		},
	});
}

export async function waitForViewport(): Promise<Viewport> {
	if (viewport) {
		return viewport;
	}

	return await waitForEvent("viewportCreated");
}

export function setViewportDateRange(value: ViewportDateRange): void {
	if (isEqual(viewportDateRange, value)) {
		return;
	}

	viewportDateRange = value;

	emitter.emit("viewportDateRangeUpdated", value);
}

type MoveViewportCenterOptions = {
	xOffset: number;
	yOffset: number;
};

export function moveViewportCenter({
	xOffset,
	yOffset,
}: MoveViewportCenterOptions): void {
	if (!viewport) {
		return;
	}

	const xPos = viewport.position.x;
	const yPos = viewport.position.y;

	viewport.position.set(xPos + xOffset, yPos + yOffset);
}

async function startViewportDateRange(): Promise<void> {
	const viewport = await waitForViewport();

	updateViewportDateRange();

	viewport.on("moved", () => updateViewportDateRange());
}

async function updateViewportDateRange(): Promise<void> {
	const range = await getViewportDateRange();

	if (!range) {
		return;
	}

	setViewportDateRange(range);
}

async function getViewportDateRange(): Promise<ViewportDateRange | null> {
	const viewport = await waitForViewport();
	const scale = await waitForScale();
	const start = scale.invert(viewport.left);
	const end = scale.invert(viewport.right);

	if (start instanceof Date && end instanceof Date) {
		return [start, end];
	}

	return null;
}

export async function updateViewportFromDateRange(
	value: ViewportDateRange | undefined,
): Promise<void> {
	const range = await getViewportDateRange();
	const settings = await waitForSettings();

	if (value === undefined || settings.isDependency() || isEqual(value, range)) {
		return;
	}

	const viewport = await waitForViewport();
	const scale = await waitForScale();
	const [start, end] = value;
	const left = scale(start);
	const right = scale(end);
	const centerX = left + (right - left) / 2;

	setViewportDateRange(value);

	viewport.fitWidth(right - left, true);
	viewport.moveCenter(centerX, viewport.center.y);
}

async function resizeViewport(): Promise<void> {
	const application = await waitForApplication();
	const viewport = await waitForViewport();
	const stage = await waitForStage();

	const originalWidth = viewport.screenWidth;
	const originalHeight = viewport.screenHeight;
	const newWidth = stage.clientWidth;
	const newHeight = stage.clientHeight;
	const xOffset = (newWidth - originalWidth) / 2;
	const yOffset = (newHeight - originalHeight) / 2;

	viewport.resize(application.screen.width, application.screen.height);

	moveViewportCenter({
		xOffset,
		yOffset,
	});
}
