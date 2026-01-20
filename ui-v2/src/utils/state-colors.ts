import type { components } from "@/api/prefect";

type StateType = components["schemas"]["StateType"];

/**
 * Default state colors (matches CSS variable defaults).
 * Used as fallback and for chart libraries that need hex values at initialization.
 */
export const STATE_COLORS: Record<StateType, string> = {
	COMPLETED: "#219D4B",
	FAILED: "#DE0529",
	RUNNING: "#09439B",
	CANCELLED: "#333333",
	CANCELLING: "#334863",
	CRASHED: "#EA580C",
	PAUSED: "#726576",
	PENDING: "#8E8093",
	SCHEDULED: "#E08504",
};

/**
 * Gets the computed state color from CSS variables.
 * Useful for canvas/chart libraries that need hex values.
 * Falls back to default colors if CSS variables are not loaded.
 */
export function getStateColor(state: StateType, shade = 600): string {
	if (typeof document === "undefined") {
		return STATE_COLORS[state];
	}
	const cssVar = `--state-${state.toLowerCase()}-${shade}`;
	const computed = getComputedStyle(document.documentElement)
		.getPropertyValue(cssVar)
		.trim();
	return computed || STATE_COLORS[state];
}

/**
 * Gets all state colors for chart initialization.
 * Call this after component mounts to get current color mode values.
 */
export function getAllStateColors(shade = 600): Record<StateType, string> {
	const states: StateType[] = [
		"COMPLETED",
		"FAILED",
		"RUNNING",
		"CANCELLED",
		"CANCELLING",
		"CRASHED",
		"PAUSED",
		"PENDING",
		"SCHEDULED",
	];
	return Object.fromEntries(
		states.map((state) => [state, getStateColor(state, shade)]),
	) as Record<StateType, string>;
}
