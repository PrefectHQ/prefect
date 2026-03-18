import {
	type RunGraphNode,
	type RunGraphNodeKind,
	type RunGraphStateEvent,
	runGraphNodeKinds,
} from "@/graphs/models";

export type GraphSelectionPosition = {
	x: number;
	y: number;
	width: number;
	height: number;
};

export type NodeSelection = {
	kind: RunGraphNode["kind"];
	id: string;
};
export function isNodeSelection(
	selection: GraphItemSelection,
): selection is NodeSelection {
	return runGraphNodeKinds.includes(selection.kind as RunGraphNodeKind);
}

export type ArtifactSelection = {
	kind: "artifact";
	id: string;
};
export function isArtifactSelection(
	selection: GraphItemSelection,
): selection is ArtifactSelection {
	return selection.kind === "artifact";
}

export type ArtifactsSelection = {
	kind: "artifacts";
	ids: string[];
	position?: GraphSelectionPosition;
};
export function isArtifactsSelection(
	selection: GraphItemSelection,
): selection is ArtifactsSelection {
	return selection.kind === "artifacts";
}

export interface StateSelection extends RunGraphStateEvent {
	kind: "state";
	position?: GraphSelectionPosition;
}
export function isStateSelection(
	selection: GraphItemSelection,
): selection is StateSelection {
	return selection.kind === "state";
}

export type EventSelection = {
	id: string;
	occurred: Date;
	kind: "event";
	position?: GraphSelectionPosition;
};
export function isEventSelection(
	selection: GraphItemSelection,
): selection is EventSelection {
	return selection.kind === "event";
}

export type EventsSelection = {
	kind: "events";
	occurred: Date | null;
	ids: string[];
	position?: GraphSelectionPosition;
};
export function isEventsSelection(
	selection: GraphItemSelection,
): selection is EventsSelection {
	return selection.kind === "events";
}

export type GraphItemSelection =
	| NodeSelection
	| ArtifactSelection
	| ArtifactsSelection
	| StateSelection
	| EventSelection
	| EventsSelection;
