import { type ColorSource, Container } from "pixi.js";
import { rectangleFactory } from "@/graphs/factories/rectangle";
import type { RunGraphStateEvent } from "@/graphs/models/states";
import { waitForApplication, waitForViewport } from "@/graphs/objects";
import { emitter } from "@/graphs/objects/events";
import { waitForRunData } from "@/graphs/objects/nodes";
import { waitForScale } from "@/graphs/objects/scale";
import { isSelected, selectItem } from "@/graphs/objects/selection";
import { layout } from "@/graphs/objects/settings";
import { waitForStyles } from "@/graphs/objects/styles";

export type FlowRunStateFactory = Awaited<
	ReturnType<typeof flowRunStateFactory>
>;

type FlowRunStateFactoryRenderProps = {
	end: Date;
};

type StateRectangleRenderProps = {
	x: number;
	width: number;
	background: ColorSource;
};

// eslint-disable-next-line @typescript-eslint/explicit-function-return-type
export async function flowRunStateFactory(state: RunGraphStateEvent) {
	const application = await waitForApplication();
	const viewport = await waitForViewport();
	const styles = await waitForStyles();
	const data = await waitForRunData();
	let scale = await waitForScale();

	const element = new Container();
	const bar = await rectangleFactory();
	const area = await rectangleFactory();

	let end: Date | null = null;
	let hovered = false;
	let selected = false;

	// The area is added to the stage so it sits behind other content,
	// where we otherwise want the bar to be on top.
	application.stage.addChild(area);

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
	bar.on("click", () => {
		const position = {
			x: bar.position.x,
			y: bar.position.y,
			width: bar.width,
			height: bar.height,
		};

		selectItem({ ...state, kind: "state", position });
	});

	emitter.on("viewportMoved", () => render());
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

	function render(newOptions?: FlowRunStateFactoryRenderProps): void {
		const { end: newEnd } = newOptions ?? {};

		if (newEnd) {
			end = newEnd;
		}

		if (data.end_time) {
			stopTicking();
		}
		if (!layout.isTemporal()) {
			area.visible = false;
			element.visible = false;
			return;
		}

		const options = getRenderStyles();

		renderBar(options);
		renderArea(options);

		area.visible = true;
		element.visible = true;
	}

	function getRenderStyles(): StateRectangleRenderProps {
		const { background = "#fff" } = styles.state(state);

		const x = Math.max(
			scale(state.timestamp) * viewport.scale._x + viewport.worldTransform.tx,
			0,
		);

		let width = 0;

		if (state.type === "RUNNING" && !data.end_time) {
			width =
				scale(new Date()) * viewport.scale._x + viewport.worldTransform.tx - x;
		} else if (end) {
			width = scale(end) * viewport.scale._x + viewport.worldTransform.tx - x;
		} else {
			width = application.screen.width - x;
		}

		return {
			x,
			width: Math.max(width, 0),
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
		bar.y = application.screen.height - height;
		bar.width = width;
		bar.height = height;
		bar.tint = background;
	}

	function renderArea({
		x,
		width,
		background,
	}: StateRectangleRenderProps): void {
		if (state.type === "RUNNING") {
			area.visible = false;
			return;
		}

		const { flowStateBarHeight, flowStateAreaAlpha } = styles;

		area.x = x;
		area.y = 0;
		area.width = width;
		area.height = application.screen.height - flowStateBarHeight;
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
	};
}
