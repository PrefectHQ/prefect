import { Container, Culler, Rectangle } from "pixi.js";
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

let viewportCullingEnabled = false;
let stageContainer: Container | null = null;
let labelCuller: VisibilityCull | null = null;
let iconCuller: VisibilityCull | null = null;
let toggleCuller: VisibilityCull | null = null;
let edgeCuller: VisibilityCull | null = null;

export async function startCulling(): Promise<void> {
	const viewport = await waitForViewport();
	const application = await waitForApplication();

	viewportCullingEnabled = true;
	stageContainer = application.stage;

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
			// Use PixiJS v8 native culling via Culler.shared
			const { screen } = application;
			Culler.shared.cull(
				application.stage,
				new Rectangle(screen.x, screen.y, screen.width, screen.height),
			);

			viewport.dirty = false;
		}
	});

	emitter.emit("cullReady", true);
	emitter.emit("labelCullCreated", labelCuller);
	emitter.emit("iconCullCreated", labelCuller);
	emitter.emit("edgeCullCreated", edgeCuller);
	emitter.emit("toggleCullCreated", toggleCuller);
}

export function stopCulling(): void {
	viewportCullingEnabled = false;
	stageContainer = null;
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

function restoreRenderable(container: Container): void {
	if (container.cullable) {
		container.renderable = true;
	}

	for (const child of container.children) {
		if (child instanceof Container) {
			restoreRenderable(child);
		}
	}
}

export function uncull(): void {
	// Restore all cullable children to renderable so bounds calculations include them.
	// The next cull() pass will re-evaluate visibility based on the viewport.
	if (stageContainer) {
		restoreRenderable(stageContainer);
	}
}

export async function waitForCull(): Promise<boolean> {
	if (viewportCullingEnabled) {
		return viewportCullingEnabled;
	}

	return await waitForEvent("cullReady");
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
