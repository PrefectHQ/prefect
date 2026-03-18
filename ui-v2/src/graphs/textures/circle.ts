import { Graphics, type RenderTexture } from "pixi.js";
import { DEFAULT_TEXTURE_RESOLUTION } from "@/graphs/consts";
import { waitForApplication } from "@/graphs/objects/application";
import { cache } from "@/graphs/objects/cache";

export type CircleStyle = {
	radius: number;
};

async function texture({ radius }: CircleStyle): Promise<RenderTexture> {
	const application = await waitForApplication();

	const circle = new Graphics().circle(0, 0, radius).fill("#fff");

	const generatedTexture = application.renderer.generateTexture({
		target: circle,
		resolution: DEFAULT_TEXTURE_RESOLUTION,
	});

	return generatedTexture as RenderTexture;
}

export async function getCircleTexture(
	style: CircleStyle,
): Promise<RenderTexture> {
	return await cache(texture, [style]);
}
