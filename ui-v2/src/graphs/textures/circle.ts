import { Graphics, type Texture } from "pixi.js";
import { DEFAULT_TEXTURE_RESOLUTION } from "@/graphs/consts";
import { waitForApplication } from "@/graphs/objects/application";
import { cache } from "@/graphs/objects/cache";

export type CircleStyle = {
	radius: number;
};

async function texture({ radius }: CircleStyle): Promise<Texture> {
	const application = await waitForApplication();

	const circle = new Graphics();
	circle.circle(0, 0, radius).fill("#fff");

	const texture = application.renderer.generateTexture({
		target: circle,
		resolution: DEFAULT_TEXTURE_RESOLUTION,
	});

	return texture;
}

export async function getCircleTexture(
	style: CircleStyle,
): Promise<Texture> {
	return await cache(texture, [style]);
}
