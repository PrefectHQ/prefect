import { CircularProgressBar, type MaskedProgressBarOptions } from "@pixi/ui";
import { waitForIconCull } from "@/graphs/objects/culling";

type CircularProgressBarOptions = {
	cullAtZoomThreshold?: boolean;
} & Partial<MaskedProgressBarOptions>;

// eslint-disable-next-line @typescript-eslint/explicit-function-return-type
export async function circularProgressBarFactory(
	options: CircularProgressBarOptions = {},
) {
	const cull = await waitForIconCull();
	const element = new CircularProgressBar({
		fillColor: 0xffffff,
		cullAtZoomThreshold: true,
		backgroundColor: 0x000000,
		backgroundAlpha: 1,
		value: 50,
		cap: "round",
		fillAlpha: 1,
		lineWidth: 20,
		radius: 50,
		...options,
	});

	if (options.cullAtZoomThreshold) {
		cull.add(element);
	}

	function render(
		data: Partial<MaskedProgressBarOptions> &
			Pick<MaskedProgressBarOptions, "lineWidth" | "radius" | "value">,
	): CircularProgressBar {
		element.progress = data.value ?? 0;

		const size = (data.radius + data.lineWidth) * 2;
		element.width = size;
		element.height = size;
		// normalize position from center to the top-left corner
		element.position.set(size / 2);

		return element;
	}

	return {
		element,
		render,
	};
}
