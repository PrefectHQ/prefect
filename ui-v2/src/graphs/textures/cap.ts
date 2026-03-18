import { Graphics, Rectangle, type Texture } from "pixi.js";
import { DEFAULT_TEXTURE_RESOLUTION } from "@/graphs/consts";
import { waitForApplication } from "@/graphs/objects/application";
import { cache } from "@/graphs/objects/cache";

export type CapStyle = {
	height: number;
	radius: number;
};

async function texture({ height, radius }: CapStyle): Promise<Texture> {
	const application = await waitForApplication();

	const graphic = new Graphics();
	graphic.beginFill("#fff");
	graphic.drawRoundedRect(0, 0, radius * 2, height, radius);
	graphic.endFill();

	const cap = application.renderer.generateTexture(graphic, {
		// drew a rounded rectangle and then just using half of the graphic to get just the left "cap"
		region: new Rectangle(0, 0, radius, height),
		resolution: DEFAULT_TEXTURE_RESOLUTION,
	});

	return cap;
}

export async function getCapTexture(style: CapStyle): Promise<Texture> {
	return await cache(texture, [style]);
}
