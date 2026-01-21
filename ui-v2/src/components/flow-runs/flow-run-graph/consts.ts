import type { StateType } from "@prefecthq/graphs";

/**
 * Shade values for each state type, used with getStateColor().
 * Different states use different shades for visual distinction.
 * See: ui-v2/src/index.css for the CSS variable definitions.
 */
export const stateTypeShades: Record<StateType, number> = {
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
