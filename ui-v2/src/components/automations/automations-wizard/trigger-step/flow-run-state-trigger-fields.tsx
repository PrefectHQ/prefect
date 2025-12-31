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

type MatchRelated = Record<string, string | string[]> | undefined;

function extractFlowIdsFromMatchRelated(matchRelated: MatchRelated): string[] {
	if (!matchRelated) return [];

	const resourceIds = matchRelated["prefect.resource.id"];
	if (!resourceIds) return [];

	const ids = Array.isArray(resourceIds) ? resourceIds : [resourceIds];
	return ids
		.filter((id) => id.startsWith("prefect.flow."))
		.map((id) => id.replace("prefect.flow.", ""));
}

function extractTagsFromMatchRelated(matchRelated: MatchRelated): string[] {
	if (!matchRelated) return [];

	const resourceIds = matchRelated["prefect.resource.id"];
	if (!resourceIds) return [];

	const ids = Array.isArray(resourceIds) ? resourceIds : [resourceIds];
	return ids
		.filter((id) => id.startsWith("prefect.tag."))
		.map((id) => id.replace("prefect.tag.", ""));
}

function buildMatchRelated(flowIds: string[], tags: string[]): MatchRelated {
	const resourceIds: string[] = [
		...flowIds.map((id) => `prefect.flow.${id}`),
		...tags.map((tag) => `prefect.tag.${tag}`),
	];

	if (resourceIds.length === 0) {
		return undefined;
	}

	return {
		"prefect.resource.role": "flow",
		"prefect.resource.id": resourceIds,
	};
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
							const selectedStates = (field.value ?? []) as StateName[];
							return (
								<FormControl>
									<StateMultiSelect
										selectedStates={selectedStates}
										onStateChange={(states) => {
											field.onChange(states);
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
