import { type ColorSource, Container } from "pixi.js";
import type { FlowRunStateFactory } from "@/graphs/factories/flowRunState";
import { rectangleFactory } from "@/graphs/factories/rectangle";
import type { RunGraphStateEvent } from "@/graphs/models/states";
import { waitForApplication, waitForViewport } from "@/graphs/objects";
import { emitter } from "@/graphs/objects/events";
import { waitForRunData } from "@/graphs/objects/nodes";
import { waitForScale } from "@/graphs/objects/scale";
import { isSelected, selectItem } from "@/graphs/objects/selection";
import { layout } from "@/graphs/objects/settings";
import { waitForStyles } from "@/graphs/objects/styles";

export type NodeFlowRunStateFactory = Awaited<
	ReturnType<typeof nodeFlowRunStateFactory>
>;

export function isNodeFlowRunStateFactory(
	factory: NodeFlowRunStateFactory | FlowRunStateFactory,
): factory is NodeFlowRunStateFactory {
	return "isNodesFlowRunStateFactory" in factory;
}

export type NodeFlowRunStateFactoryRenderProps = {
	end?: Date;
	parentStartDate?: Date;
	width?: number;
	height?: number;
};

type StateRectangleRenderProps = {
	x: number;
	width: number;
	background: ColorSource;
};

// eslint-disable-next-line @typescript-eslint/explicit-function-return-type
export async function nodeFlowRunStateFactory(state: RunGraphStateEvent) {
	const application = await waitForApplication();
	const viewport = await waitForViewport();
	const styles = await waitForStyles();
	const data = await waitForRunData();
	let scale = await waitForScale();

	const element = new Container();
	const bar = await rectangleFactory();
	const area = await rectangleFactory();

	let end: Date | null = null;
	let parentStart: Date | null = null;
	let parentWidth = 0;
	let parentHeight = 0;
	let hovered = false;
	let selected = false;

	element.visible = false;
	element.addChild(area);
	element.addChild(bar);

	bar.eventMode = "static";
	bar.cursor = "pointer";
	bar.on("mouseover", () => {
		hovered = true;
		render();
	});
	bar.on("mouseleave", () => {
		hovered = false;
		render();
	});
	bar.on("click", (clickEvent) => {
		clickEvent.stopPropagation();
		const barPosition = bar.getGlobalPosition();

		const position = {
			x: barPosition.x,
			y: barPosition.y,
			width: bar.width * viewport.scale.x,
			height: bar.height * viewport.scale.y,
		};

		selectItem({ ...state, kind: "state", position });
	});

	area.eventMode = "none";
	area.cursor = "default";

	emitter.on("scaleUpdated", (updated) => {
		scale = updated;
		render();
	});
	emitter.on("itemSelected", () => {
		const isCurrentlySelected = isSelected({ kind: "state", ...state });

		if (isCurrentlySelected !== selected) {
			selected = isCurrentlySelected;
			// clear the hovered state to account for the popover div
			// that prevents the mouseleave event in prefect-ui-library
			hovered = false;
			render();
		}
	});

	if (state.type === "RUNNING" && !data.end_time) {
		startTicking();
	}

	function render(props?: NodeFlowRunStateFactoryRenderProps): void {
		const { end: newEnd, parentStartDate, width, height } = props ?? {};

		if (newEnd) {
			end = newEnd;
		}
		if (parentStartDate) {
			parentStart = parentStartDate;
		}
		if (width) {
			parentWidth = width;
		}
		if (height) {
			parentHeight = height;
		}

		if (data.end_time) {
			stopTicking();
		}

		if (!layout.isTemporal()) {
			element.visible = false;
			return;
		}

		if (!parentStart || parentWidth <= 0) {
			element.visible = false;
			return;
		}

		const options = getRenderStyles();

		if (options.width <= 0) {
			element.visible = false;
			return;
		}

		renderBar(options);
		renderArea(options);

		element.visible = true;
	}

	function getRenderStyles(): StateRectangleRenderProps {
		const { background = "#fff" } = styles.state(state);

		if (!parentStart) {
			return {
				x: 0,
				width: 0,
				background,
			};
		}

		const parentStartX = scale(parentStart);
		let startX = scale(state.timestamp) - parentStartX;

		if (startX >= parentWidth) {
			return {
				x: parentWidth,
				width: 0,
				background,
			};
		}

		if (startX < 0) {
			startX = 0;
		}

		let endX = scale(end ?? new Date()) - parentStartX;

		if (endX > parentWidth) {
			endX = parentWidth;
		}

		const width = Math.max(endX - startX, 0);

		return {
			x: startX,
			width,
			background,
		};
	}

	function renderBar({
		x,
		width,
		background,
	}: StateRectangleRenderProps): void {
		const { flowStateBarHeight, flowStateSelectedBarHeight } = styles;

		const height =
			hovered || selected ? flowStateSelectedBarHeight : flowStateBarHeight;

		bar.x = x;
		bar.y = parentHeight - height;
		bar.width = width;
		bar.height = height;
		bar.tint = background;
	}

	function renderArea({
		x,
		width,
		background,
	}: StateRectangleRenderProps): void {
		const { flowStateBarHeight, flowStateAreaAlpha, nodeHeight } = styles;

		const topOffset = nodeHeight / 2;

		area.x = x;
		area.y = topOffset;
		area.width = width;
		area.height = parentHeight - flowStateBarHeight - topOffset;
		area.tint = background;
		area.alpha = flowStateAreaAlpha;
	}

	function startTicking(): void {
		application.ticker.add(tick);
	}

	function stopTicking(): void {
		application.ticker.remove(tick);
	}

	function tick(): void {
		render();
	}

	return {
		element,
		render,
		isNodesFlowRunStateFactory: true,
	};
}
