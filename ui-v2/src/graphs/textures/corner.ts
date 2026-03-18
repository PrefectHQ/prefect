import { Graphics, Rectangle, type Texture } from "pixi.js";
import { waitForApplication } from "@/graphs/objects/application";
import { cache } from "@/graphs/objects/cache";

export type CornerStyle = {
	size: number;
	radius?: number;
	stroke?: number;
};

async function texture({
	size,
	stroke = 1,
	radius = 0,
}: CornerStyle): Promise<Texture> {
	const application = await waitForApplication();

	const graphic = new Graphics();
	graphic.lineStyle(stroke, "#fff", 1, 0);
	graphic.drawRoundedRect(0, 0, size * 2, size * 2, radius);

	const arrow = application.renderer.generateTexture(graphic, {
		// drew a rounded rectangle and then just using one corner as the "arrow"
		region: new Rectangle(0, 0, size, size),

		// manually bumping up the resolution to keep the border radius from being blurry
		resolution: 10,
	});

	return arrow;
}

export async function getCornerTexture(style: CornerStyle): Promise<Texture> {
	return await cache(texture, [style]);
}
