import type {
	HorizontalPositionSettings,
	VerticalPositionSettings,
} from "@/graphs/factories/position";
import {
	getHorizontalDomain,
	getHorizontalRange,
	layout,
} from "@/graphs/objects/settings";

export function horizontalSettingsFactory(
	startTime: Date,
): HorizontalPositionSettings {
	return {
		mode: layout.horizontal,
		range: getHorizontalRange(),
		domain: getHorizontalDomain(startTime),
	};
}

export function verticalSettingsFactory(): VerticalPositionSettings {
	return {
		mode: layout.vertical,
	};
}
