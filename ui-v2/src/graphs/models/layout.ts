export type Pixels = { x: number; y: number };
export type VerticalMode = "waterfall" | "nearest-parent" | "duration-sorted";
export type HorizontalMode = "temporal" | "dependency" | "left-aligned";

export function isVerticalMode(value: string): value is VerticalMode {
	return ["waterfall", "nearest-parent", "duration-sorted"].includes(value);
}

export function isHorizontalMode(value: string): value is HorizontalMode {
	return ["temporal", "dependency", "left-aligned"].includes(value);
}

export type NodeSize = {
	height: number;
	width: number;
};

export type LayoutSettings = {
	horizontal: HorizontalMode;
	vertical: VerticalMode;
	horizontalScaleMultiplierDefault: number;
	horizontalScaleMultiplier: number;
	disableAnimations: boolean;
	disableGuides: boolean;
	disableEdges: boolean;
	disableArtifacts: boolean;
	disableEvents: boolean;
	isTemporal: () => boolean;
	isDependency: () => boolean;
	isWaterfall: () => boolean;
	isNearestParent: () => boolean;
	isLeftAligned: () => boolean;
};

export type NodeWidths = Map<string, number>;

export type NodeLayoutResponse = {
	x: number;
	y: number;
	column: number;
	row: number;
};

export type NodesLayoutResponse = {
	maxRow: number;
	maxColumn: number;
	positions: Map<string, NodeLayoutResponse>;
};
