import type {
	RequiredGraphConfig,
	RunGraphConfig,
} from "@/graphs/models/RunGraph";
import { emitter, waitForEvent } from "@/graphs/objects/events";

let config: RequiredGraphConfig | null = null;

const defaults: Omit<RequiredGraphConfig, "runId" | "fetch" | "styles"> = {
	animationDuration: 500,
	disableAnimationsThreshold: 500,
	disableEdgesThreshold: 500,
	fetchEvents: () => [],
	fetchEventsInterval: 30000,
	theme: "dark",
};

function withDefaults(config: RunGraphConfig): RequiredGraphConfig {
	return {
		...defaults,
		...config,
	};
}

export function startConfig(config: RunGraphConfig): void {
	setConfig(config);
}

export function setConfig(value: RunGraphConfig): void {
	const newConfig = withDefaults(value);

	if (!config) {
		config = newConfig;
		emitter.emit("configCreated", newConfig);
		return;
	}

	Object.assign(config, newConfig);
	emitter.emit("configUpdated", newConfig);
}

export function stopConfig(): void {
	config = null;
}

export async function waitForConfig(): Promise<RequiredGraphConfig> {
	if (config) {
		return config;
	}

	return await waitForEvent("configCreated");
}
