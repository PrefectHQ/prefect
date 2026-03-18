import { Sprite } from "pixi.js";
import { type CapStyle, getCapTexture } from "@/graphs/textures/cap";

type CapSprites = {
	left: Sprite;
	right: Sprite;
};

// eslint-disable-next-line @typescript-eslint/explicit-function-return-type
export function capFactory() {
	const left = new Sprite();
	const right = new Sprite();

	async function render(style: CapStyle): Promise<CapSprites> {
		const texture = await getCapTexture(style);
		left.texture = texture;
		right.texture = texture;

		right.anchor.x = 1;
		right.scale.x = -1;

		return {
			left,
			right,
		};
	}

	return {
		left,
		right,
		render,
	};
}
