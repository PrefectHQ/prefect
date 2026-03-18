import { Container } from "pixi.js";
import { ArrowDirection, arrowFactory } from "@/graphs/factories/arrow";
import { barFactory } from "@/graphs/factories/bar";
import { borderFactory } from "@/graphs/factories/border";
import { waitForLabelCull } from "@/graphs/objects/culling";
import { waitForStyles } from "@/graphs/objects/styles";

type NodeArrowBarStyles = {
	inside: boolean;
	isOpen: boolean;
};

// eslint-disable-next-line @typescript-eslint/explicit-function-return-type
export async function nodeArrowButtonFactory() {
	const styles = await waitForStyles();
	const cull = await waitForLabelCull();
	const container = new Container();
	const { element: arrow, render: renderArrow } = await arrowFactory();
	const { element: bar, render: renderBar } = await barFactory();
	const { element: border, render: renderBorder } = await borderFactory();

	cull.add(container);

	let isInside = false;

	container.eventMode = "static";
	container.cursor = "pointer";
	container.addChild(bar);
	container.addChild(arrow);
	container.addChild(border);

	container.on("mouseover", onMouseover);
	container.on("mouseout", onMouseout);

	async function render({
		inside,
		isOpen,
	}: NodeArrowBarStyles): Promise<Container> {
		isInside = inside;

		const arrowStyles = {
			size: 10,
			stroke: 2,
			rotate: isOpen ? ArrowDirection.Up : ArrowDirection.Down,
		};

		const arrow = await renderArrow(arrowStyles);

		const buttonStyles = {
			width: styles.nodeToggleSize,
			height: styles.nodeToggleSize,
			background: styles.nodeToggleBgColor,
			radius: styles.nodeToggleBorderRadius,
		};

		const bar = await renderBar(buttonStyles);

		bar.alpha = inside ? 0 : 0.5;

		const border = await renderBorder({
			width: buttonStyles.width,
			height: buttonStyles.height,
			radius: buttonStyles.radius,
			stroke: 1,
			color: styles.nodeToggleBorderColor,
		});

		border.alpha = inside ? 0 : 1;

		const middle = {
			y: bar.height / 2,
			x: bar.width / 2,
		};

		const offset = arrowStyles.size / 4;

		arrow.x = middle.x;
		arrow.y = isOpen ? middle.y + offset : middle.y - offset;

		return container;
	}

	function onMouseover(): void {
		bar.alpha = isInside ? 0.5 : 1;
	}

	function onMouseout(): void {
		bar.alpha = isInside ? 0 : 0.5;
	}

	return {
		element: container,
		render,
	};
}
