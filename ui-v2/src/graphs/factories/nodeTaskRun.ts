import {
	DEFAULT_NESTED_GRAPH_BORDER_Z_INDEX,
	DEFAULT_NESTED_GRAPH_NODE_Z_INDEX,
	DEFAULT_NESTED_GRAPH_NODES_Z_INDEX,
	DEFAULT_NODE_LABEL_Z_INDEX,
} from "@/graphs/consts";
import { borderFactory } from "@/graphs/factories/border";
import { nodeLabelFactory } from "@/graphs/factories/label";
import { nodeArrowButtonFactory } from "@/graphs/factories/nodeArrowButton";
import { nodeBarFactory } from "@/graphs/factories/nodeBar";
import { nodesContainerFactory } from "@/graphs/factories/nodes";
import { BoundsContainer } from "@/graphs/models/boundsContainer";
import type { NodeSize } from "@/graphs/models/layout";
import type { RunGraphData, RunGraphNode } from "@/graphs/models/RunGraph";
import { waitForConfig } from "@/graphs/objects/config";
import { cull } from "@/graphs/objects/culling";
import { layout } from "@/graphs/objects/settings";
import { waitForStyles } from "@/graphs/objects/styles";

export type TaskRunContainer = Awaited<
	ReturnType<typeof taskRunContainerFactory>
>;

// eslint-disable-next-line @typescript-eslint/explicit-function-return-type
export async function taskRunContainerFactory(
	node: RunGraphNode,
	nestedGraphData: RunGraphData | undefined,
) {
	const config = await waitForConfig();
	const styles = await waitForStyles();
	const container = new BoundsContainer();
	const { element: label, render: renderLabelText } = await nodeLabelFactory();
	const { element: border, render: renderBorderContainer } =
		await borderFactory();
	const { element: bar, render: renderBar } = await nodeBarFactory();
	const { element: arrowButton, render: renderArrowButtonContainer } =
		await nodeArrowButtonFactory();
	const {
		element: nodesContainer,
		render: renderNodes,
		getSize: getNodesSize,
		stopWorker: stopNodesWorker,
	} = await nodesContainerFactory();

	container.addChild(bar);
	container.addChild(label);

	let isOpen = false;
	let internalNode = node;
	let internalNestedGraphData = nestedGraphData;

	container.sortableChildren = true;

	border.zIndex = DEFAULT_NESTED_GRAPH_BORDER_Z_INDEX;
	bar.zIndex = DEFAULT_NESTED_GRAPH_NODE_Z_INDEX;
	label.zIndex = DEFAULT_NODE_LABEL_Z_INDEX;
	arrowButton.zIndex = DEFAULT_NODE_LABEL_Z_INDEX;
	nodesContainer.zIndex = DEFAULT_NESTED_GRAPH_NODES_Z_INDEX;

	border.eventMode = "none";
	border.cursor = "default";

	nodesContainer.position = {
		x: 0,
		y: styles.nodeHeight + styles.nodesPadding,
	};

	nodesContainer.on("rendered", () => {
		cull();
		resized();
	});

	arrowButton.on("click", (event) => {
		event.stopPropagation();
		toggle();
	});

	async function render(
		newNodeData: RunGraphNode,
		newNestedGraph: RunGraphData | undefined,
	): Promise<BoundsContainer> {
		internalNode = newNodeData;
		internalNestedGraphData = newNestedGraph;

		if (newNestedGraph) {
			container.addChild(arrowButton);
		}

		await renderBar(newNodeData);

		if (newNestedGraph) {
			await renderArrowButton();
		}

		if (isOpen) {
			if (newNestedGraph) {
				renderNodes(newNestedGraph);
			}

			await renderBorder();
		}

		await renderLabel();

		return container;
	}

	async function renderArrowButton(): Promise<BoundsContainer> {
		const buttonSize = styles.nodeToggleSize;
		const offset = styles.nodeHeight - buttonSize;
		const inside = bar.width > buttonSize;

		const container = await renderArrowButtonContainer({
			inside,
			isOpen,
		});

		container.x = inside ? offset / 2 : bar.width + styles.nodePadding;
		container.y = offset / 2;

		return container;
	}

	async function renderLabel(): Promise<BoundsContainer> {
		const label = await renderLabelText(internalNode.label);
		const colorOnNode =
			config.theme === "dark" ? styles.textDefault : styles.textInverse;

		const padding = styles.nodePadding;
		const rightOfButton = arrowButton.x + arrowButton.width + padding;
		const rightOfBar = bar.width + padding;
		const inside = bar.width > rightOfButton + label.width + padding;

		const y = styles.nodeHeight / 2 - label.height / 2;
		const x = inside ? rightOfButton : Math.max(rightOfBar, rightOfButton);

		label.position = { x, y };
		label.tint = inside ? colorOnNode : styles.textDefault;

		return label;
	}

	async function renderBorder(): Promise<void> {
		const { background = "#fff" } = styles.node(internalNode);
		const { width, height: nodeHeights } = getNodesSize();
		const { height: nodeLayersHeight } = getSize();
		const { nodeBorderRadius } = styles;

		const strokeWidth = 2;
		border.position = { x: -strokeWidth, y: -strokeWidth };

		const height = layout.isTemporal()
			? nodeLayersHeight + strokeWidth * 2
			: nodeHeights + strokeWidth * 2;

		await renderBorderContainer({
			width: width + strokeWidth * 2,
			height,
			stroke: strokeWidth,
			radius: [nodeBorderRadius, nodeBorderRadius, 0, 0],
			color: background,
		});
	}

	async function toggle(): Promise<void> {
		if (!isOpen) {
			await open();
		} else {
			await close();
		}
	}

	async function open(): Promise<void> {
		isOpen = true;
		container.addChild(nodesContainer);
		container.addChild(border);

		if (!internalNestedGraphData) {
			throw new Error("Attempted to open without nested graph data");
		}

		await Promise.all([
			renderNodes(internalNestedGraphData),
			render(internalNode, internalNestedGraphData),
		]);

		resized();
	}

	async function close(): Promise<void> {
		isOpen = false;
		container.removeChild(nodesContainer);
		container.removeChild(border);

		stopNodesWorker();

		await render(internalNode, internalNestedGraphData);

		resized();
	}

	function getSize(): NodeSize {
		const nodes = getNodesSize();
		const { nodeHeight, nodesPadding } = styles;

		const nodesHeight = isOpen ? nodes.height + nodesPadding * 2 : 0;
		const nodesWidth = isOpen ? nodes.width : 0;
		const flowRunNodeHeight = nodeHeight;

		return {
			height: flowRunNodeHeight + nodesHeight,
			width: Math.max(nodesWidth, container.width),
		};
	}

	function resized(): void {
		if (isOpen) {
			renderBorder();
		}

		const size = getSize();

		container.emit("resized", size);
	}

	return {
		kind: "task-run" as const,
		element: container,
		render,
		bar,
	};
}
