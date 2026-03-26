import { type ScaleLinear, type ScaleTime, scaleLinear, scaleTime } from "d3";
import type { HorizontalMode, VerticalMode } from "@/graphs/models/layout";

export type VerticalPositionSettings = {
	mode: VerticalMode;
};

export type HorizontalPositionSettings = {
	mode: HorizontalMode;
	range: [number, number];
	domain: [Date, Date] | [number, number];
};

export type HorizontalScale = ReturnType<typeof horizontalScaleFactory>;

export function horizontalScaleFactory(
	settings: HorizontalPositionSettings,
): ScaleTime<number, number> | ScaleLinear<number, number> {
	if (settings.mode === "temporal" || settings.mode === "left-aligned") {
		return getTimeScale(settings);
	}

	return getLinearScale(settings);
}

function getTimeScale({
	domain,
	range,
}: HorizontalPositionSettings): ScaleTime<number, number> {
	return scaleTime().domain(domain).range(range);
}

function getLinearScale({
	domain,
	range,
}: HorizontalPositionSettings): ScaleLinear<number, number> {
	return scaleLinear().domain(domain).range(range);
}
