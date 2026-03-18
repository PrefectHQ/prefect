import { type ColorSource, Container } from "pixi.js";
import { capFactory } from "@/graphs/factories/cap";
import { rectangleFactory } from "@/graphs/factories/rectangle";

export type BarStyle = {
	width: number;
	height: number;
	background: ColorSource;
	radius: number;
	capLeft?: boolean;
	capRight?: boolean;
};

// eslint-disable-next-line @typescript-eslint/explicit-function-return-type
export async function barFactory() {
	const bar = new Container();
	const rectangle = await rectangleFactory();
	const { left, right, render: renderCaps } = await capFactory();

	bar.addChild(rectangle);
	bar.addChild(left);
	bar.addChild(right);

	async function render(style: BarStyle): Promise<Container> {
		const { width, x, visible } = getRectangleStyles(style);

		await renderCaps({
			height: style.height,
			radius: style.radius,
		});

		rectangle.visible = visible;
		rectangle.width = width;
		rectangle.height = style.height;
		rectangle.x = x;

		left.visible = getCapVisibility(style.capLeft, style.radius);
		right.visible = getCapVisibility(style.capRight, style.radius);

		right.x = style.radius + width;

		rectangle.tint = style.background;
		left.tint = style.background;
		right.tint = style.background;

		return bar;
	}

	function getCapVisibility(
		enabled: boolean | undefined,
		radius: number,
	): boolean {
		if (radius === 0) {
			return false;
		}

		return enabled ?? true;
	}

	function getRectangleStyles(style: BarStyle): {
		width: number;
		x: number;
		visible: boolean;
	} {
		const left = getCapVisibility(style.capLeft, style.radius);
		const right = getCapVisibility(style.capRight, style.radius);

		let caps = 0;

		if (left) {
			caps += style.radius;
		}

		if (right) {
			caps += style.radius;
		}

		const width = Math.max(style.width - caps, 0);
		const visible = width > 0;
		const x = left ? style.radius : 0;

		return {
			width,
			visible,
			x,
		};
	}

	return {
		element: bar,
		render,
	};
}
