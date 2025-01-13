import { createContext } from "react";

/**
 * Context for managing tooltip state across multiple charts.
 * Only one tooltip can be active at a time, controlled by a holder ID.
 *
 * @property currentHolder - Unique identifier of the chart currently displaying a tooltip
 * @property takeCurrentHolder - Function to set the current tooltip holder
 * @property releaseCurrentHolder - Function to release the current tooltip holder if it matches
 */
export const FlowRunActivityBarGraphTooltipContext = createContext<{
	currentHolder?: string;
	takeCurrentHolder: (holder: string) => void;
	releaseCurrentHolder: (holder: string) => void;
}>({
	takeCurrentHolder: () => {},
	releaseCurrentHolder: () => {},
});
