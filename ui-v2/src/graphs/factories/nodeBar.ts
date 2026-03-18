import { differenceInMilliseconds } from "date-fns";
import { millisecondsInSecond } from "date-fns/constants";
import { Container } from "pixi.js";
import { barFactory } from "@/graphs/factories/bar";
import { selectedBorderFactory } from "@/graphs/factories/selectedBorder";
import type { RunGraphNode } from "@/graphs/models/RunGraph";
import { isSelected } from "@/graphs/objects/selection";
import {
	getHorizontalColumnSize,
	layout,
	waitForSettings,
} from "@/graphs/objects/settings";
import { waitForStyles } from "@/graphs/objects/styles";

// eslint-disable-next-line @typescript-eslint/explicit-function-return-type
export async function nodeBarFactory() {
	const styles = await waitForStyles();
	const settings = await waitForSettings();
	const container = new Container();
	const { element: bar, render: renderBar } = await barFactory();
	const { element: border, render: renderBorder } =
		await selectedBorderFactory();

	container.addChild(bar);
	container.addChild(border);

	async function render(node: RunGraphNode): Promise<Container> {
		const { background = "#fff" } = styles.node(node);
		const { nodeHeight: height, nodeRadius: radius } = styles;
		const selected = isSelected({ kind: node.kind, id: node.id });
		const width = getTotalWidth(node, radius);

		const capRight = node.state_type !== "RUNNING" || settings.isDependency();

		await Promise.all([
			renderBar({
				width,
				height,
				radius,
				background,
				capRight,
			}),
			renderBorder({ selected, width, height }),
		]);

		return bar;
	}

	function getTotalWidth(node: RunGraphNode, borderRadius: number): number {
		const columnSize = getHorizontalColumnSize();

		if (layout.isTemporal() || layout.isLeftAligned()) {
			const right = node.start_time;
			const left = node.end_time ?? new Date();
			const seconds =
				differenceInMilliseconds(left, right) / millisecondsInSecond;
			const width = seconds * columnSize;

			return Math.max(width, borderRadius * 2);
		}

		return columnSize;
	}

	return {
		element: container,
		render,
	};
}
