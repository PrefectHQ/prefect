import type { ComponentType, SVGProps } from "react";
import type { components } from "@/api/prefect";
import { FlowRunStateTypeEmptyAwaitingImage } from "./flow-run-state-type-empty-awaiting-image";
import { FlowRunStateTypeEmptyBadTerminalImage } from "./flow-run-state-type-empty-bad-terminal-image";
import { FlowRunStateTypeEmptyGoodTerminalImage } from "./flow-run-state-type-empty-good-terminal-image";
import { FlowRunStateTypeEmptyLiveImage } from "./flow-run-state-type-empty-live-image";

type StateType = components["schemas"]["StateType"];

type FlowRunStateTypeEmptyProps = {
	/** State types that are being filtered */
	stateTypes: StateType[];
};

/**
 * Returns the appropriate image component based on the state types.
 * Priority order matches the Vue implementation:
 * 1. Failed/Crashed -> Bad terminal image (green - indicates no failures is good)
 * 2. Running/Pending/Cancelling -> Live image (blue)
 * 3. Completed -> Good terminal image (red - indicates no completions)
 * 4. Scheduled/Paused -> Awaiting image (yellow/orange)
 */
function getImageComponent(
	stateTypes: StateType[],
): ComponentType<SVGProps<SVGSVGElement>> | null {
	const lowerStates = stateTypes.map((s) => s.toLowerCase());

	if (lowerStates.includes("failed") || lowerStates.includes("crashed")) {
		return FlowRunStateTypeEmptyBadTerminalImage;
	}

	if (
		lowerStates.includes("running") ||
		lowerStates.includes("pending") ||
		lowerStates.includes("cancelling")
	) {
		return FlowRunStateTypeEmptyLiveImage;
	}

	if (lowerStates.includes("completed")) {
		return FlowRunStateTypeEmptyGoodTerminalImage;
	}

	if (lowerStates.includes("scheduled") || lowerStates.includes("paused")) {
		return FlowRunStateTypeEmptyAwaitingImage;
	}

	return null;
}

/**
 * Empty state component shown when there are no flow runs for the selected state type.
 */
export function FlowRunStateTypeEmpty({
	stateTypes,
}: FlowRunStateTypeEmptyProps) {
	// Format state types for display
	const formattedStates = stateTypes.map((state) => {
		// Convert state type to lowercase for display
		// Handle special case for SCHEDULED -> "late"
		if (state === "SCHEDULED") {
			return "late";
		}
		return state.toLowerCase();
	});

	// Format the list with "or" conjunction
	const formatter = new Intl.ListFormat("en", {
		style: "long",
		type: "disjunction",
	});
	const statesString = formatter.format(formattedStates);

	const ImageComponent = getImageComponent(stateTypes);

	return (
		<div className="flex flex-col items-center gap-8 my-20">
			{ImageComponent && <ImageComponent className="h-32" />}
			<p className="text-lg text-center max-w-xs">
				You currently have 0 {statesString} runs.
			</p>
		</div>
	);
}
