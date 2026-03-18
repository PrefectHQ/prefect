import { playheadFactory } from "@/graphs/factories/playhead";
import { waitForApplication } from "@/graphs/objects/application";
import { emitter } from "@/graphs/objects/events";
import { waitForRunData } from "@/graphs/objects/nodes";

export async function startPlayhead(): Promise<void> {
	const application = await waitForApplication();
	const data = await waitForRunData();
	const { element: playhead, render } = await playheadFactory();

	if (!data.end_time) {
		application.stage.addChild(playhead);
		application.ticker.add(render);
	}

	emitter.on("runDataUpdated", ({ end_time }) => {
		if (end_time) {
			application.ticker.remove(render);
			application.stage.removeChild(playhead);
		}
	});
}

export function stopPlayhead(): void {
	// do nothing
}
