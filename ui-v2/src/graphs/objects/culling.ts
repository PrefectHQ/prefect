import { ViewportCull } from "@/graphs/services/viewportCull";
import {
	DEFAULT_EDGE_CULLING_THRESHOLD,
	DEFAULT_ICON_CULLING_THRESHOLD,
	DEFAULT_LABEL_CULLING_THRESHOLD,
	DEFAULT_TOGGLE_CULLING_THRESHOLD,
} from "@/graphs/consts";
import { waitForApplication } from "@/graphs/objects/application";
import { emitter, waitForEvent } from "@/graphs/objects/events";
import { waitForViewport } from "@/graphs/objects/viewport";
import { VisibilityCull } from "@/graphs/services/visibilityCull";

let viewportCuller: ViewportCull | null = null;
let labelCuller: VisibilityCull | null = null;
let iconCuller: VisibilityCull | null = null;
let toggleCuller: VisibilityCull | null = null;
let edgeCuller: VisibilityCull | null = null;

export async function startCulling(): Promise<void> {
	const viewport = await waitForViewport();
	const application = await waitForApplication();

	// this cull uses renderable so any other custom logic for showing or hiding must use
	// the "visible" property or this will interfere
	viewportCuller = new ViewportCull({
		toggle: "renderable",
	});

	labelCuller = new VisibilityCull();
	iconCuller = new VisibilityCull();
	edgeCuller = new VisibilityCull();
	toggleCuller = new VisibilityCull();

	application.ticker.add(() => {
		if (viewport.dirty) {
			const edgesVisible = viewport.scale.x > DEFAULT_EDGE_CULLING_THRESHOLD;
			const labelsVisible = viewport.scale.x > DEFAULT_LABEL_CULLING_THRESHOLD;
			const iconsVisible = viewport.scale.x > DEFAULT_ICON_CULLING_THRESHOLD;
			const togglesVisible =
				viewport.scale.x > DEFAULT_TOGGLE_CULLING_THRESHOLD;

			edgeCuller?.toggle(edgesVisible);
			labelCuller?.toggle(labelsVisible);
			iconCuller?.toggle(iconsVisible);
			toggleCuller?.toggle(togglesVisible);
			viewportCuller?.cull(application.renderer.screen);

			viewport.dirty = false;
		}
	});

	emitter.emit("cullCreated", viewportCuller);
	emitter.emit("labelCullCreated", labelCuller);
	emitter.emit("iconCullCreated", labelCuller);
	emitter.emit("edgeCullCreated", edgeCuller);
	emitter.emit("toggleCullCreated", toggleCuller);
}

export function stopCulling(): void {
	viewportCuller = null;
	labelCuller?.clear();
	labelCuller = null;
	iconCuller?.clear();
	iconCuller = null;
	edgeCuller?.clear();
	edgeCuller = null;
	toggleCuller?.clear();
	toggleCuller = null;
}

export async function cull(): Promise<void> {
	const viewport = await waitForViewport();

	viewport.dirty = true;
}

export function uncull(): void {
	if (viewportCuller) {
		viewportCuller.uncull();
	}
}

export async function waitForCull(): Promise<ViewportCull> {
	if (viewportCuller) {
		return viewportCuller;
	}

	return await waitForEvent("cullCreated");
}

export async function waitForEdgeCull(): Promise<VisibilityCull> {
	if (edgeCuller) {
		return edgeCuller;
	}

	return await waitForEvent("edgeCullCreated");
}

export async function waitForLabelCull(): Promise<VisibilityCull> {
	if (labelCuller) {
		return labelCuller;
	}

	return await waitForEvent("labelCullCreated");
}

export async function waitForIconCull(): Promise<VisibilityCull> {
	if (iconCuller) {
		return iconCuller;
	}

	return await waitForEvent("iconCullCreated");
}

export async function waitForToggleCull(): Promise<VisibilityCull> {
	if (toggleCuller) {
		return toggleCuller;
	}

	return await waitForEvent("toggleCullCreated");
}
