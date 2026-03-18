import { Container } from "pixi.js";
import { borderFactory } from "@/graphs/factories/border";
import { waitForStyles } from "@/graphs/objects/styles";

type SelectedBorderFactoryRenderProps = {
	selected: boolean;
	width: number;
	height: number;
};

// eslint-disable-next-line @typescript-eslint/explicit-function-return-type
export async function selectedBorderFactory() {
	const styles = await waitForStyles();
	const container = new Container();
	const { element: border, render: renderBorder } = await borderFactory();

	async function render({
		selected,
		width,
		height,
	}: SelectedBorderFactoryRenderProps): Promise<Container> {
		if (!selected) {
			container.removeChild(border);
			return container;
		}

		const {
			selectedBorderColor,
			selectedBorderWidth,
			selectedBorderOffset,
			selectedBorderRadius,
		} = styles;

		border.position.set(-selectedBorderOffset, -selectedBorderOffset);
		container.addChild(border);

		await renderBorder({
			stroke: selectedBorderWidth,
			radius: selectedBorderRadius,
			width: width + selectedBorderOffset * 2,
			height: height + selectedBorderOffset * 2,
			color: selectedBorderColor,
		});

		return container;
	}

	return {
		element: container,
		render,
	};
}
