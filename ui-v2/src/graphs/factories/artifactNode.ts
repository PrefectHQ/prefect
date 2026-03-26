import { Container } from "pixi.js";
import { artifactBarFactory } from "@/graphs/factories/artifactBar";
import { circularProgressBarFactory } from "@/graphs/factories/circularProgressBar";
import { iconFactory } from "@/graphs/factories/icon";
import { nodeLabelFactory } from "@/graphs/factories/label";
import {
	type ArtifactType,
	artifactTypeIconMap,
	type RunGraphArtifactTypeAndData,
} from "@/graphs/models";
import { waitForStyles } from "@/graphs/objects/styles";

type ArtifactNodeFactoryOptions = {
	cullAtZoomThreshold?: boolean;
};

type ArtifactNodeFactoryRenderOptions = {
	selected?: boolean;
	name?: string;
	type: ArtifactType;
} & RunGraphArtifactTypeAndData;

// eslint-disable-next-line @typescript-eslint/explicit-function-return-type
export async function artifactNodeFactory({
	cullAtZoomThreshold,
}: ArtifactNodeFactoryOptions) {
	const styles = await waitForStyles();

	const element = new Container();
	const content = new Container();
	const { element: icon, render: renderIcon } = await iconFactory({
		cullAtZoomThreshold,
	});
	const { element: circularProgressBar, render: renderCircularProgressbar } =
		await circularProgressBarFactory();
	const { element: label, render: renderLabel } = await nodeLabelFactory({
		cullAtZoomThreshold,
	});
	const { element: bar, render: renderBar } = await artifactBarFactory();

	let selected = false;
	let name: string | null = null;
	let type: ArtifactType;

	content.addChild(label);
	element.addChild(bar);
	element.addChild(content);

	async function render(
		options: ArtifactNodeFactoryRenderOptions,
	): Promise<Container> {
		const { selected: newSelected, name: newName, type: newType } = options;
		selected = newSelected ?? selected;
		name = newName ?? name;
		type = newType;
		if (type === "progress") {
			content.addChild(circularProgressBar);
		} else {
			content.addChild(icon);
		}

		if (options.type === "progress") {
			await Promise.all([
				renderProgressArtifact(options.data),
				renderArtifactNode(),
			]);
		} else {
			await Promise.all([renderArtifactIcon(), renderArtifactNode()]);
		}

		await renderBg();

		return element;
	}

	async function renderArtifactIcon(): Promise<Container> {
		if (type === "progress") {
			return icon;
		}

		const iconName = artifactTypeIconMap[type];
		const {
			artifactIconSize,
			artifactIconColor,
			artifactPaddingLeft,
			artifactPaddingY,
		} = styles;

		const newIcon = await renderIcon(iconName);

		newIcon.position = { x: artifactPaddingLeft, y: artifactPaddingY };
		newIcon.width = artifactIconSize;
		newIcon.height = artifactIconSize;
		newIcon.tint = artifactIconColor;

		return newIcon;
	}

	// eslint-disable-next-line require-await
	async function renderProgressArtifact(data: number): Promise<Container> {
		const {
			artifactPaddingLeft,
			artifactPaddingRight,
			artifactPaddingY,
			artifactIconSize,
		} = styles;

		const lineWidth = 20;
		const radius = (artifactIconSize - lineWidth * 2) / 2;
		const newDynamicArtifact = renderCircularProgressbar({
			value: data,
			radius,
			lineWidth,
		});

		if (name) {
			newDynamicArtifact.position.x += artifactPaddingLeft;
		} else {
			// Without a name/text label, uneven left/right padding should be normalized
			// so that the progress bar is centered
			newDynamicArtifact.position.x +=
				(artifactPaddingLeft + artifactPaddingRight) / 2;
		}
		newDynamicArtifact.position.y += artifactPaddingY;

		return circularProgressBar;
	}

	async function renderArtifactNode(): Promise<Container> {
		if (!name) {
			label.visible = false;
			return label;
		}

		await renderLabel(name);

		const {
			artifactPaddingLeft,
			artifactPaddingY,
			artifactTextColor,
			artifactIconSize,
			artifactContentGap,
		} = styles;

		const contentGap = name ? artifactContentGap : 0;
		const x = artifactPaddingLeft + artifactIconSize + contentGap;
		const y = artifactPaddingY;

		label.tint = artifactTextColor;
		label.scale.set(0.75);
		label.position = { x, y };
		label.visible = true;

		return label;
	}

	async function renderBg(): Promise<Container> {
		const { artifactPaddingLeft, artifactPaddingRight, artifactPaddingY } =
			styles;

		const options = {
			selected: selected,
			width: content.width + artifactPaddingLeft + artifactPaddingRight,
			height: content.height + artifactPaddingY * 2,
		};

		return await renderBar(options);
	}

	return {
		element,
		render,
	};
}
