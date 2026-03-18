import { Sprite } from "pixi.js";
import { type CornerStyle, getCornerTexture } from "@/graphs/textures/corner";

export enum ArrowDirection {
	Up = 0,
	Down = 180,
	Left = 270,
	Right = 90,
}

export type ArrowStyle = CornerStyle & {
	rotate?: number;
};

// eslint-disable-next-line @typescript-eslint/explicit-function-return-type
export function arrowFactory() {
	const arrow = new Sprite();

	async function render(style: ArrowStyle): Promise<Sprite> {
		const { rotate = 0 } = style;
		const cornerStyles: CornerStyle = {
			size: style.size,
			radius: style.radius,
			stroke: style.stroke,
		};
		const texture = await getCornerTexture(cornerStyles);
		arrow.texture = texture;

		arrow.anchor.set(0.5, 0.5);
		// texture is the corner of a rectangle so 45 deg defaults the arrow to pointing up
		arrow.angle = 45 + rotate;

		return arrow;
	}

	return {
		element: arrow,
		render,
	};
}
