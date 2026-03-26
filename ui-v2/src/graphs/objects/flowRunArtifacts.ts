import { DEFAULT_ROOT_ARTIFACT_Z_INDEX } from "@/graphs/consts";
import { runArtifactsFactory } from "@/graphs/factories/runArtifacts";
import type { RunGraphData } from "@/graphs/models/RunGraph";
import { waitForApplication } from "@/graphs/objects/application";
import { emitter } from "@/graphs/objects/events";
import { waitForRunData } from "@/graphs/objects/nodes";
import { layout, waitForSettings } from "@/graphs/objects/settings";

export async function startFlowRunArtifacts(): Promise<void> {
	const application = await waitForApplication();
	const data = await waitForRunData();
	const settings = await waitForSettings();
	const {
		element,
		render: renderArtifacts,
		update,
	} = await runArtifactsFactory({ isRoot: true });

	element.zIndex = DEFAULT_ROOT_ARTIFACT_Z_INDEX;

	function render(newData?: RunGraphData): void {
		if (layout.isTemporal() && !settings.disableArtifacts) {
			application.stage.addChild(element);
			renderArtifacts(newData?.artifacts);
			return;
		}

		application.stage.removeChild(element);
	}

	if (data.artifacts) {
		render(data);
	}

	emitter.on("viewportMoved", () => update());

	emitter.on("runDataCreated", (data) => render(data));
	emitter.on("runDataUpdated", (data) => render(data));
	emitter.on("configUpdated", () => render());
	emitter.on("layoutSettingsUpdated", () => render());
}

export function stopFlowRunArtifacts(): void {
	// do nothing
}
