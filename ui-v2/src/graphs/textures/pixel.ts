import { Graphics, type RenderTexture } from "pixi.js";
import { waitForApplication } from "@/graphs/objects/application";
import { cache } from "@/graphs/objects/cache";

async function texture(): Promise<RenderTexture> {
	const application = await waitForApplication();

	const rectangle = new Graphics().rect(0, 0, 1, 1).fill("#fff");

	const generatedTexture = application.renderer.generateTexture({
		target: rectangle,
		textureSourceOptions: {
			addressMode: "repeat",
		},
	});

	return generatedTexture as RenderTexture;
}

export async function getPixelTexture(): Promise<RenderTexture> {
	return await cache(texture, []);
}
