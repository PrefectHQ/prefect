import { Container } from "pixi.js";
import { barFactory } from "@/graphs/factories/bar";
import { selectedBorderFactory } from "@/graphs/factories/selectedBorder";
import { waitForStyles } from "@/graphs/objects/styles";

type ArtifactBarFactoryRenderProps = {
	selected: boolean;
	width: number;
	height: number;
};

// eslint-disable-next-line @typescript-eslint/explicit-function-return-type
export async function artifactBarFactory() {
	const styles = await waitForStyles();
	const container = new Container();
	const { element: bar, render: renderBar } = await barFactory();
	const { element: border, render: renderBorder } =
		await selectedBorderFactory();

	container.addChild(bar);
	container.addChild(border);

	async function render({
		selected,
		width,
		height,
	}: ArtifactBarFactoryRenderProps): Promise<Container> {
		const { artifactBgColor, artifactBorderRadius } = styles;

		const barStyle = {
			width,
			height,
			background: artifactBgColor,
			radius: artifactBorderRadius,
			capLeft: true,
			capRight: true,
		};

		await Promise.all([
			renderBar(barStyle),
			renderBorder({ selected, width, height }),
		]);

		return container;
	}

	return {
		element: container,
		render,
	};
}
