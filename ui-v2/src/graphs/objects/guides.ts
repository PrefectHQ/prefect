import { guidesFactory } from "@/graphs/factories/guides";
import { waitForApplication } from "@/graphs/objects/application";
import { emitter } from "@/graphs/objects/events";

export async function startGuides(): Promise<void> {
	const application = await waitForApplication();
	const { element, render } = await guidesFactory();

	application.stage.addChild(element);

	render();

	emitter.on("viewportDateRangeUpdated", () => render());
	emitter.on("layoutSettingsUpdated", () => render());
	emitter.on("configUpdated", () => render());
}

export function stopGuides(): void {
	// nothing to stop
}
