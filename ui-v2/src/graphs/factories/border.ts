import { type ColorSource, Container, Sprite } from "pixi.js";
import { getCornerTexture } from "@/graphs/textures/corner";
import { getPixelTexture } from "@/graphs/textures/pixel";

export type BorderStyle = {
	width: number;
	height: number;
	stroke: number;
	radius?: number | [number, number, number, number];
	color?: ColorSource;
};

type CornerMeasurement = {
	size: number;
	radius: number;
};

type CornerMeasurements = {
	topLeft: CornerMeasurement;
	topRight: CornerMeasurement;
	bottomLeft: CornerMeasurement;
	bottomRight: CornerMeasurement;
};

// eslint-disable-next-line @typescript-eslint/explicit-function-return-type
export function borderFactory() {
	const container = new Container();
	const topLeft = new Sprite();
	const topRight = new Sprite();
	const bottomLeft = new Sprite();
	const bottomRight = new Sprite();
	const left = new Sprite();
	const right = new Sprite();
	const top = new Sprite();
	const bottom = new Sprite();

	topLeft.name = "border-corner-top-left";
	topRight.name = "border-corner-top-right";
	bottomLeft.name = "border-corner-bottom-left";
	bottomRight.name = "border-corner-bottom-right";
	left.name = "border-corner-left";
	right.name = "border-corner-right";
	top.name = "border-corner-top";
	bottom.name = "border-corner-bottom";

	topRight.anchor.x = 1;
	topRight.scale.x = -1;
	bottomLeft.anchor.y = 1;
	bottomLeft.scale.y = -1;
	bottomRight.anchor.x = 1;
	bottomRight.scale.x = -1;
	bottomRight.anchor.y = 1;
	bottomRight.scale.y = -1;

	container.addChild(topLeft);
	container.addChild(topRight);
	container.addChild(bottomLeft);
	container.addChild(bottomRight);
	container.addChild(left);
	container.addChild(right);
	container.addChild(top);
	container.addChild(bottom);

	async function render(style: BorderStyle): Promise<Container> {
		const { radius = 0, color = "#fff", stroke, width, height } = style;

		const fixedRadius = typeof radius === "number";

		const cornerSizes: CornerMeasurements = {
			topLeft: getCornerDimensions(
				fixedRadius ? radius : radius[0],
				width,
				height,
			),
			topRight: getCornerDimensions(
				fixedRadius ? radius : radius[1],
				width,
				height,
			),
			bottomLeft: getCornerDimensions(
				fixedRadius ? radius : radius[2],
				width,
				height,
			),
			bottomRight: getCornerDimensions(
				fixedRadius ? radius : radius[3],
				width,
				height,
			),
		};

		await updateCorners({
			width,
			height,
			stroke,
			cornerSizes,
		});

		await updateBorders({
			width,
			height,
			stroke,
			cornerSizes,
		});

		setTint(color);

		return container;
	}

	function getCornerDimensions(
		radius: number,
		width: number,
		height: number,
	): CornerMeasurement {
		const maxSize = Math.min(width, height);
		const size = radius * 2 > maxSize ? maxSize / 2 : radius;

		return {
			size,
			radius,
		};
	}

	type UpdateCorners = {
		width: number;
		height: number;
		stroke: number;
		cornerSizes: CornerMeasurements;
	};

	async function updateCorners({
		width,
		height,
		stroke,
		cornerSizes,
	}: UpdateCorners): Promise<void> {
		const {
			topLeft: topLeftSize,
			topRight: topRightSize,
			bottomLeft: bottomLeftSize,
			bottomRight: bottomRightSize,
		} = cornerSizes;

		const [
			topLeftTexture,
			topRightTexture,
			bottomRightText,
			bottomLeftTexture,
		] = await Promise.all([
			getCornerTexture({ ...topLeftSize, stroke }),
			getCornerTexture({ ...topRightSize, stroke }),
			getCornerTexture({ ...bottomLeftSize, stroke }),
			getCornerTexture({ ...bottomRightSize, stroke }),
		]);

		topLeft.texture = topLeftTexture;
		topRight.texture = topRightTexture;
		bottomLeft.texture = bottomLeftTexture;
		bottomRight.texture = bottomRightText;

		topLeft.position.set(0, 0);
		topRight.position.set(width - topRightSize.size, 0);
		bottomLeft.position.set(0, height - bottomLeftSize.size);
		bottomRight.position.set(
			width - bottomRightSize.size,
			height - bottomRightSize.size,
		);
	}

	type UpdateBorders = {
		width: number;
		height: number;
		stroke: number;
		cornerSizes: CornerMeasurements;
	};

	async function updateBorders({
		width,
		height,
		stroke,
		cornerSizes,
	}: UpdateBorders): Promise<void> {
		const texture = await getPixelTexture();

		const { topLeft, topRight, bottomLeft, bottomRight } = cornerSizes;

		top.texture = texture;
		left.texture = texture;
		right.texture = texture;
		bottom.texture = texture;

		left.position.set(0, topLeft.size);
		left.height = Math.max(height - topLeft.size - bottomLeft.size, 0);
		left.width = stroke;

		right.position.set(width - stroke, topRight.size);
		right.height = Math.max(height - topRight.size - bottomRight.size, 0);
		right.width = stroke;

		top.position.set(topLeft.size, 0);
		top.width = Math.max(width - topLeft.size - topRight.size, 0);
		top.height = stroke;

		bottom.position.set(bottomLeft.size, height - stroke);
		bottom.width = Math.max(width - bottomLeft.size - bottomRight.size, 0);
		bottom.height = stroke;
	}

	function setTint(color: ColorSource): void {
		topLeft.tint = color;
		topRight.tint = color;
		bottomLeft.tint = color;
		bottomRight.tint = color;
		top.tint = color;
		left.tint = color;
		right.tint = color;
		bottom.tint = color;
	}

	return {
		element: container,
		render,
	};
}
