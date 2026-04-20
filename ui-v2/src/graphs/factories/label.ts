import type { BitmapText } from "pixi.js";
import { waitForLabelCull } from "@/graphs/objects/culling";
import { waitForFonts } from "@/graphs/objects/fonts";

type NodeLabelFactoryOptions = {
	cullAtZoomThreshold?: boolean;
};

// eslint-disable-next-line @typescript-eslint/explicit-function-return-type
export async function nodeLabelFactory({
	cullAtZoomThreshold = true,
}: NodeLabelFactoryOptions = {}) {
	const font = await waitForFonts();
	const cull = await waitForLabelCull();

	const label = font("");

	if (cullAtZoomThreshold) {
		cull.add(label);
	}

	async function render(text: string): Promise<BitmapText> {
		label.text = text;

		return await label;
	}

	return {
		element: label,
		render,
	};
}
