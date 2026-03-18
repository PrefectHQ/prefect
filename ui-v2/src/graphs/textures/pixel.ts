import { Graphics, type Texture } from "pixi.js";
import { waitForApplication } from "@/graphs/objects/application";
import { cache } from "@/graphs/objects/cache";

async function texture(): Promise<Texture> {
	const application = await waitForApplication();

	const rectangle = new Graphics();
	rectangle.rect(0, 0, 1, 1).fill("#fff");

	const generated = application.renderer.generateTexture({
		target: rectangle,
	});

	generated.source.style.addressMode = "repeat";

	return generated;
}

export async function getPixelTexture(): Promise<Texture> {
	return await cache(texture, []);
}
