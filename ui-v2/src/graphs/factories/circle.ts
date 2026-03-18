import { Sprite } from "pixi.js";
import { type CircleStyle, getCircleTexture } from "@/graphs/textures/circle";

export async function circleFactory(style: CircleStyle): Promise<Sprite> {
	const texture = await getCircleTexture(style);

	return new Sprite(texture);
}
