import {
	type HorizontalScale,
	horizontalScaleFactory,
} from "@/graphs/factories/position";
import { horizontalSettingsFactory } from "@/graphs/factories/settings";
import { type EventKey, emitter, waitForEvent } from "@/graphs/objects/events";
import { waitForRunData } from "@/graphs/objects/nodes";
import { waitForSettings } from "@/graphs/objects/settings";

let scale: HorizontalScale | null = null;

export async function startScale(): Promise<void> {
	const data = await waitForRunData();

	setHorizontalScale(data.start_time);

	emitter.on("layoutSettingsUpdated", () =>
		setHorizontalScale(data.start_time),
	);
}

export function stopScale(): void {
	scale = null;
}

export async function waitForScale(): Promise<HorizontalScale> {
	if (scale) {
		return scale;
	}

	return await waitForEvent("scaleCreated");
}

async function setHorizontalScale(startTime: Date): Promise<void> {
	// makes sure the initial horizontal scale multiplier is set prior to creating this scale
	await waitForSettings();

	const event: EventKey = scale ? "scaleUpdated" : "scaleCreated";
	const settings = horizontalSettingsFactory(startTime);

	scale = horizontalScaleFactory(settings);

	emitter.emit(event, scale);
}
