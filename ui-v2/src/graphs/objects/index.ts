import type { RunGraphConfig } from "@/graphs/models/RunGraph";
import {
	startApplication,
	stopApplication,
} from "@/graphs/objects/application";
import { startCache, stopCache } from "@/graphs/objects/cache";
import { startConfig, stopConfig } from "@/graphs/objects/config";
import { startCulling, stopCulling } from "@/graphs/objects/culling";
import { emitter } from "@/graphs/objects/events";
import {
	startFlowRunArtifacts,
	stopFlowRunArtifacts,
} from "@/graphs/objects/flowRunArtifacts";
import {
	startFlowRunEvents,
	stopFlowRunEvents,
} from "@/graphs/objects/flowRunEvents";
import {
	startFlowRunStates,
	stopFlowRunStates,
} from "@/graphs/objects/flowRunStates";
import { startFonts, stopFonts } from "@/graphs/objects/fonts";
import { startGuides, stopGuides } from "@/graphs/objects/guides";
import { startNodes, stopNodes } from "@/graphs/objects/nodes";
import { startPlayhead, stopPlayhead } from "@/graphs/objects/playhead";
import { startScale, stopScale } from "@/graphs/objects/scale";
import { startSelection, stopSelection } from "@/graphs/objects/selection";
import { startSettings, stopSettings } from "@/graphs/objects/settings";
import { startStage, stopStage } from "@/graphs/objects/stage";
import { startStyles, stopStyles } from "@/graphs/objects/styles";
import { startViewport, stopViewport } from "@/graphs/objects/viewport";

export * from "./application";
export * from "./config";
export * from "./events";
export * from "./selection";
export * from "./settings";
export * from "./stage";
export * from "./viewport";

type StartParameters = {
	stage: HTMLDivElement;
	config: RunGraphConfig;
};

export function start({ stage, config }: StartParameters): void {
	startApplication();
	startViewport();
	startScale();
	startGuides();
	startNodes();
	startFlowRunArtifacts();
	startFlowRunEvents();
	startFlowRunStates();
	startPlayhead();
	startFonts();
	startStage(stage);
	startConfig(config);
	startStyles();
	startCulling();
	startSettings();
	startSelection();
	startCache();
}

export function stop(): void {
	emitter.clear();

	try {
		stopApplication();
		stopViewport();
		stopScale();
		stopGuides();
		stopStage();
		stopNodes();
		stopFlowRunArtifacts();
		stopFlowRunEvents();
		stopFlowRunStates();
		stopPlayhead();
		stopConfig();
		stopStyles();
		stopFonts();
		stopCulling();
		stopSettings();
		stopSelection();
		stopCache();
	} catch (error) {
		console.error(error);
	}
}
