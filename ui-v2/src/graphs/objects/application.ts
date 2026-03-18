import { Application } from "pixi.js";
import { emitter, waitForEvent } from "@/graphs/objects/events";
import { waitForStage } from "@/graphs/objects/stage";

export let application: Application | null = null;

export async function startApplication(): Promise<void> {
	const stage = await waitForStage();

	await createApplication(stage);

	emitter.on("stageUpdated", resizeApplication);
}

export function stopApplication(): void {
	if (!application) {
		return;
	}

	application.destroy(true, {
		children: true,
	});

	application = null;
}

async function createApplication(stage: HTMLDivElement): Promise<void> {
	if (application) {
		return;
	}

	application = new Application();

	// PixiJS v8 requires async initialization before accessing properties
	await application.init({
		backgroundAlpha: 0,
		resizeTo: stage,
		antialias: true,
		resolution: Math.ceil(window.devicePixelRatio),
	});

	// for setting the viewport above the guides
	application.stage.sortableChildren = true;

	stage.appendChild(application.canvas);

	emitter.emit("applicationCreated", application);

	if (process.env.NODE_ENV === "development") {
		// For whatever reason typing globalThis is not quite working and not worth the time to fix for devtools
		// eslint-disable-next-line @typescript-eslint/no-explicit-any
		(globalThis as any).__PIXI_APP__ = application;
	}
}

export async function waitForApplication(): Promise<Application> {
	if (application) {
		return application;
	}

	return await waitForEvent("applicationCreated");
}

function resizeApplication(stage: HTMLDivElement): void {
	if (!application) {
		return;
	}

	application.resizeTo = stage;
	emitter.emit("applicationResized", application);
}
