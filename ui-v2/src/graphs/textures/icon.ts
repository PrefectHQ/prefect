import { type IBaseTextureOptions, Texture } from "pixi.js";
import { DEFAULT_TEXT_RESOLUTION } from "@/graphs/consts";
import type { IconName } from "@/graphs/models/icon";
import { cache } from "@/graphs/objects/cache";
import * as prefectIcons from "@/graphs/textures/icons";

function texture(icon: IconName): Texture {
	const options: IBaseTextureOptions = {
		resolution: DEFAULT_TEXT_RESOLUTION,
	};

	// eslint-disable-next-line import/namespace
	const iconTexture = Texture.from(prefectIcons[icon], options);

	return iconTexture;
}

export async function getIconTexture(icon: IconName): Promise<Texture> {
	return await cache(texture, [icon]);
}
