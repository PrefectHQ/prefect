import type { components } from "@/api/prefect";

type StateType = components["schemas"]["StateType"];

type FlowRunStateTypeEmptyProps = {
	/** State types that are being filtered */
	stateTypes: StateType[];
};

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

	return (
		<div className="flex flex-col items-center justify-center py-8 text-center">
			<p className="text-sm text-muted-foreground">
				You currently have 0 {statesString} runs.
			</p>
		</div>
	);
}
