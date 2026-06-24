import { useFormContext, useWatch } from "react-hook-form";
import type { StateName } from "@/api/flow-runs/constants";
import type { AutomationWizardSchema } from "@/components/automations/automations-wizard/automation-schema";
import { FlowMultiSelect } from "@/components/flows/flow-multi-select";
import { DurationInput } from "@/components/ui/duration-input";
import {
	FormControl,
	FormField,
	FormItem,
	FormLabel,
	FormMessage,
} from "@/components/ui/form";
import { TagsInput } from "@/components/ui/tags-input";
import { PostureSelect } from "./posture-select";
import { StateMultiSelect } from "./state-multi-select";

type MatchRelatedObject = Record<string, string | string[]>;
type MatchRelated = MatchRelatedObject | MatchRelatedObject[] | undefined;

// Convert state names to event strings (e.g., "Completed" -> "prefect.flow-run.Completed")
// When no states selected, returns wildcard ["prefect.flow-run.*"] (Vue behavior)
function toStateNameEvents(stateNames: StateName[]): string[] {
	if (stateNames.length === 0) {
		return ["prefect.flow-run.*"];
	}
	return stateNames.map((name) => `prefect.flow-run.${name}`);
}

// Convert event strings back to state names (e.g., "prefect.flow-run.Completed" -> "Completed")
// Wildcard "prefect.flow-run.*" returns empty array (means "any state")
function fromStateNameEvents(events: string[] | undefined): StateName[] {
	if (!events || events.length === 0) {
		return [];
	}
	if (events.includes("prefect.flow-run.*")) {
		return [];
	}
	return events
		.filter((event) => event.startsWith("prefect.flow-run."))
		.map((event) => event.replace("prefect.flow-run.", "") as StateName);
}

function asMatchRelatedArray(matchRelated: MatchRelated): MatchRelatedObject[] {
	if (!matchRelated) return [];
	return Array.isArray(matchRelated) ? matchRelated : [matchRelated];
}

function extractFlowIdsFromMatchRelated(matchRelated: MatchRelated): string[] {
	const objects = asMatchRelatedArray(matchRelated);
	const ids: string[] = [];
	for (const obj of objects) {
		const resourceIds = obj["prefect.resource.id"];
		if (!resourceIds) continue;
		const arr = Array.isArray(resourceIds) ? resourceIds : [resourceIds];
		ids.push(
			...arr
				.filter((id) => id.startsWith("prefect.flow."))
				.map((id) => id.replace("prefect.flow.", "")),
		);
	}
	return ids;
}

function extractTagsFromMatchRelated(matchRelated: MatchRelated): string[] {
	const objects = asMatchRelatedArray(matchRelated);
	const tags: string[] = [];
	for (const obj of objects) {
		const resourceIds = obj["prefect.resource.id"];
		if (!resourceIds) continue;
		const arr = Array.isArray(resourceIds) ? resourceIds : [resourceIds];
		tags.push(
			...arr
				.filter((id) => id.startsWith("prefect.tag."))
				.map((id) => id.replace("prefect.tag.", "")),
		);
	}
	return tags;
}

function buildMatchRelated(flowIds: string[], tags: string[]): MatchRelated {
	// Return empty object when no flows/tags selected
	if (flowIds.length === 0 && tags.length === 0) {
		return {};
	}

	// Flows use a single match_related object (OR: match any selected flow)
	if (flowIds.length > 0) {
		return {
			"prefect.resource.role": "flow",
			"prefect.resource.id": flowIds.map((id) => `prefect.flow.${id}`),
		};
	}

	// Tags use separate match_related objects (AND: match all selected tags)
	return tags.map((tag) => ({
		"prefect.resource.role": "tag",
		"prefect.resource.id": `prefect.tag.${tag}`,
	}));
}

export const FlowRunStateTriggerFields = () => {
	const form = useFormContext<AutomationWizardSchema>();
	const posture = useWatch<AutomationWizardSchema>({ name: "trigger.posture" });

	// Determine which field to use based on posture
	// Reactive: use "expect" (states to enter)
	// Proactive: use "after" (states to stay in)
	const stateFieldName =
		posture === "Proactive" ? "trigger.after" : "trigger.expect";

	const matchRelated = useWatch<AutomationWizardSchema>({
		name: "trigger.match_related",
	}) as MatchRelated;

	const selectedFlowIds = extractFlowIdsFromMatchRelated(matchRelated);
	const selectedTags = extractTagsFromMatchRelated(matchRelated);

	const handleFlowToggle = (flowId: string) => {
		const currentFlowIds = selectedFlowIds;
		const newFlowIds = currentFlowIds.includes(flowId)
			? currentFlowIds.filter((id) => id !== flowId)
			: [...currentFlowIds, flowId];

		// Clear tags when flows are selected (Vue behavior)
		const newTags = newFlowIds.length > 0 ? [] : selectedTags;
		form.setValue(
			"trigger.match_related",
			buildMatchRelated(newFlowIds, newTags),
		);
	};

	const handleTagsChange = (tags: string[]) => {
		form.setValue(
			"trigger.match_related",
			buildMatchRelated(selectedFlowIds, tags),
		);
	};

	// Hide tags input when flows are selected (Vue behavior)
	const showTagsInput = selectedFlowIds.length === 0;

	return (
		<div className="space-y-4">
			<FormItem>
				<FormLabel>Flows</FormLabel>
				<FormControl>
					<FlowMultiSelect
						selectedFlowIds={selectedFlowIds}
						onToggleFlow={handleFlowToggle}
						emptyMessage="All flows"
					/>
				</FormControl>
			</FormItem>

			{showTagsInput && (
				<FormItem>
					<FormLabel>Flow Run Tags</FormLabel>
					<FormControl>
						<TagsInput
							value={selectedTags}
							onChange={handleTagsChange}
							placeholder="All tags"
						/>
					</FormControl>
				</FormItem>
			)}

			<FormItem>
				<FormLabel>Flow Run</FormLabel>
				<div className="grid grid-cols-[10rem_1fr] gap-2">
					<PostureSelect />
					<FormField
						control={form.control}
						name={stateFieldName}
						render={({ field }) => {
							// Convert event strings to state names for UI display
							const eventStrings = field.value ?? [];
							const selectedStates = fromStateNameEvents(eventStrings);
							return (
								<FormControl>
									<StateMultiSelect
										selectedStates={selectedStates}
										onStateChange={(states) => {
											// Convert state names to event strings for storage
											field.onChange(toStateNameEvents(states));
										}}
										emptyMessage="Any state"
									/>
								</FormControl>
							);
						}}
					/>
				</div>
			</FormItem>

			{posture === "Proactive" && (
				<FormField
					control={form.control}
					name="trigger.within"
					render={({ field }) => (
						<FormItem>
							<FormLabel>For</FormLabel>
							<FormControl>
								<DurationInput
									value={field.value ?? 0}
									onChange={field.onChange}
									min={0}
								/>
							</FormControl>
							<FormMessage />
						</FormItem>
					)}
				/>
			)}
		</div>
	);
};
