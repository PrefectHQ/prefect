import { Assets, ImageSource, Texture } from "pixi.js";
import type { IconName } from "@/graphs/models/icon";
import { cache } from "@/graphs/objects/cache";
import * as prefectIcons from "@/graphs/textures/icons";

async function texture(icon: IconName): Promise<Texture> {
	// TODO: Clean this typing up
	const iconUrl = prefectIcons[icon as keyof typeof prefectIcons];

	// PixiJS v8: For data URIs (inlined by Vite in production), create texture directly from image
	// to avoid Assets cache warnings
	if (iconUrl.startsWith("data:")) {
		return new Promise((resolve, reject) => {
			const img = new Image();
			img.onload = () => {
				const source = new ImageSource({ resource: img });
				const texture = new Texture({ source });
				resolve(texture);
			};
			img.onerror = reject;
			img.src = iconUrl;
		});
	}

	// For external URLs, use Assets.load()
	const iconTexture = await Assets.load(iconUrl);

	return iconTexture;
}

export async function getIconTexture(icon: IconName): Promise<Texture> {
	return await cache(texture, [icon]);
}
