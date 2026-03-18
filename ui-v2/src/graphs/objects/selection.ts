import {
	type GraphItemSelection,
	isArtifactSelection,
	isArtifactsSelection,
	isEventSelection,
	isEventsSelection,
	isNodeSelection,
	isStateSelection,
	type NodeSelection,
} from "@/graphs/models/selection";
import { emitter } from "@/graphs/objects/events";
import { waitForViewport } from "@/graphs/objects/viewport";

let selected: GraphItemSelection | null = null;
let selectionDisabled = false;

export async function startSelection(): Promise<void> {
	const viewport = await waitForViewport();

	viewport.on("click", () => selectItem(null));

	// these drag events are to prevent selection from being cleared while dragging
	viewport.on("drag-start", () => {
		selectionDisabled = true;
	});

	viewport.on("drag-end", () => {
		// drag-end gets emitted before the click event so we delay this until the
		// the next loop so the click event doesn't dismiss the selected node
		setTimeout(() => {
			selectionDisabled = false;
		});
	});
}

export function stopSelection(): void {
	selected = null;
	selectionDisabled = false;
}

export function selectItem(item: GraphItemSelection | null): void {
	if (selectionDisabled) {
		return;
	}

	if ((!item && !selected) || (item && isSelected(item))) {
		return;
	}

	selected = item;

	if (item === null) {
		emitter.emit("itemSelected", null);
		return;
	}

	emitter.emit("itemSelected", item);
}

export function isSelected(item: GraphItemSelection): boolean {
	if (selected === null) {
		return false;
	}

	const { kind } = item;

	switch (kind) {
		case "task-run":
			return isNodeSelection(selected) && selected.id === item.id;
		case "flow-run":
			return isNodeSelection(selected) && selected.id === item.id;
		case "artifact":
			return isArtifactSelection(selected) && selected.id === item.id;
		case "artifacts":
			return (
				isArtifactsSelection(selected) &&
				selected.ids.length === item.ids.length &&
				selected.ids.every((id) => item.ids.includes(id))
			);
		case "state":
			return isStateSelection(selected) && selected.id === item.id;
		case "event":
			return isEventSelection(selected) && selected.id === item.id;
		case "events":
			return (
				isEventsSelection(selected) &&
				selected.ids.length === item.ids.length &&
				selected.ids.every((id) => item.ids.includes(id))
			);
		default: {
			const exhaustive: never = kind;
			throw new Error(`switch does not have case for value: ${exhaustive}`);
		}
	}
}

export function getSelectedRunGraphNode(): NodeSelection | null {
	if (!!selected && isNodeSelection(selected)) {
		return selected as NodeSelection;
	}

	return null;
}

export function getSelected(): GraphItemSelection | null {
	return selected;
}
