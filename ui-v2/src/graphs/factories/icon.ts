import { Sprite } from "pixi.js";
import type { IconName } from "@/graphs/models/icon";
import { waitForIconCull } from "@/graphs/objects/culling";
import { getIconTexture } from "@/graphs/textures/icon";

type IconFactoryOptions = {
	cullAtZoomThreshold?: boolean;
};

// eslint-disable-next-line @typescript-eslint/explicit-function-return-type
export async function iconFactory({
	cullAtZoomThreshold = true,
}: IconFactoryOptions = {}) {
	const cull = await waitForIconCull();
	const element = new Sprite();

	if (cullAtZoomThreshold) {
		cull.add(element);
	}

	async function render(icon: IconName): Promise<Sprite> {
		const texture = await getIconTexture(icon);

		element.texture = texture;

		return element;
	}

	return {
		element,
		render,
	};
}
