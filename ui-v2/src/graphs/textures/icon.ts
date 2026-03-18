import { Texture } from "pixi.js";
import type { IconName } from "@/graphs/models/icon";
import { cache } from "@/graphs/objects/cache";
import * as prefectIcons from "@/graphs/textures/icons";

function texture(icon: IconName): Texture {
	// eslint-disable-next-line import/namespace
	const iconTexture = Texture.from(prefectIcons[icon]);

	return iconTexture;
}

export async function getIconTexture(icon: IconName): Promise<Texture> {
	return await cache(texture, [icon]);
}
