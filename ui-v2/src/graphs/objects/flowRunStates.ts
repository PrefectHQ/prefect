import { DEFAULT_ROOT_FLOW_STATE_Z_INDEX } from "@/graphs/consts";
import { runStatesFactory } from "@/graphs/factories/runStates";
import type { RunGraphData } from "@/graphs/models";
import { waitForApplication } from "@/graphs/objects/application";
import { emitter } from "@/graphs/objects/events";
import { waitForRunData } from "@/graphs/objects/nodes";

export async function startFlowRunStates(): Promise<void> {
	const application = await waitForApplication();
	const data = await waitForRunData();
	const { element, render: renderStates } = await runStatesFactory({
		isRoot: true,
	});

	element.zIndex = DEFAULT_ROOT_FLOW_STATE_Z_INDEX;
	application.stage.addChild(element);

	function render(newData?: RunGraphData): void {
		renderStates(newData?.states);
	}

	if (data.states) {
		render(data);
	}

	emitter.on("runDataUpdated", (data) => render(data));
	emitter.on("configUpdated", () => render());
	emitter.on("layoutSettingsUpdated", () => render());
}

export function stopFlowRunStates(): void {
	// do nothing
}
