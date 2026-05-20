import type { RunGraphTheme, StateType } from "@/graphs";

/**
 * Shade values for each state type in light mode, used with getStateColor().
 * See: ui-v2/src/index.css for the CSS variable definitions.
 */
const lightModeStateTypeShades: Record<StateType, number> = {
	COMPLETED: 600,
	RUNNING: 700,
	SCHEDULED: 700,
	PENDING: 800,
	FAILED: 700,
	CANCELLED: 600,
	CANCELLING: 600,
	CRASHED: 600,
	PAUSED: 800,
};

/**
 * Shade values for each state type in dark mode.
 * Uses lower-numbered shades (darker fills in the dark-mode palette)
 * so graph nodes are visually calmer and maintain readable contrast
 * with white in-node labels.
 */
const darkModeStateTypeShades: Record<StateType, number> = {
	COMPLETED: 300,
	RUNNING: 300,
	SCHEDULED: 300,
	PENDING: 300,
	FAILED: 300,
	CANCELLED: 300,
	CANCELLING: 300,
	CRASHED: 300,
	PAUSED: 300,
};

/** @deprecated Use {@link getStateTypeShade} for theme-aware shade selection. */
export const stateTypeShades: Record<StateType, number> =
	lightModeStateTypeShades;

export function getStateTypeShade(
	stateType: StateType,
	theme: RunGraphTheme,
): number {
	const shades =
		theme === "dark" ? darkModeStateTypeShades : lightModeStateTypeShades;
	return shades[stateType];
}
