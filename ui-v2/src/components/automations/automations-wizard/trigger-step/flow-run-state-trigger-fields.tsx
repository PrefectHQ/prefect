import { useFormContext, useWatch } from "react-hook-form";
import type { components } from "@/api/prefect";
import type { AutomationWizardSchema } from "@/components/automations/automations-wizard/automation-schema";
import { FlowMultiSelect } from "@/components/flows/flow-multi-select";
import {
	FormControl,
	FormField,
	FormItem,
	FormLabel,
	FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { TagsInput } from "@/components/ui/tags-input";
import { PostureSelect } from "./posture-select";
import { StateMultiSelect } from "./state-multi-select";

type StateType = components["schemas"]["StateType"];

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
	const stateFieldLabel =
		posture === "Proactive" ? "States to stay in" : "States to enter";

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
		form.setValue(
			"trigger.match_related",
			buildMatchRelated(newFlowIds, selectedTags),
		);
	};

	const handleTagsChange = (tags: string[]) => {
		form.setValue(
			"trigger.match_related",
			buildMatchRelated(selectedFlowIds, tags),
		);
	};

	return (
		<div className="space-y-4">
			<div className="flex items-start gap-4">
				<FormItem className="flex-1">
					<FormLabel>Flows</FormLabel>
					<FormControl>
						<FlowMultiSelect
							selectedFlowIds={selectedFlowIds}
							onToggleFlow={handleFlowToggle}
							emptyMessage="Any flow"
						/>
					</FormControl>
				</FormItem>
				<FormItem className="flex-1">
					<FormLabel>Tags</FormLabel>
					<FormControl>
						<TagsInput
							value={selectedTags}
							onChange={handleTagsChange}
							placeholder="Enter tags"
						/>
					</FormControl>
				</FormItem>
			</div>

			<div className="flex items-start gap-4">
				<PostureSelect />
				<FormField
					control={form.control}
					name={stateFieldName}
					render={({ field }) => {
						const selectedStates = (field.value ?? []) as StateType[];
						return (
							<FormItem className="flex-1">
								<FormLabel>{stateFieldLabel}</FormLabel>
								<FormControl>
									<StateMultiSelect
										selectedStates={selectedStates}
										onToggleState={(state) => {
											const currentStates = selectedStates;
											if (currentStates.includes(state)) {
												field.onChange(
													currentStates.filter((s) => s !== state),
												);
											} else {
												field.onChange([...currentStates, state]);
											}
										}}
										emptyMessage="Any state"
									/>
								</FormControl>
								<FormMessage />
							</FormItem>
						);
					}}
				/>
			</div>

			<div className="flex gap-4">
				<FormField
					control={form.control}
					name="trigger.threshold"
					render={({ field }) => (
						<FormItem className="w-32">
							<FormLabel>Threshold</FormLabel>
							<FormControl>
								<Input
									type="number"
									min={1}
									{...field}
									onChange={(e) => field.onChange(Number(e.target.value))}
								/>
							</FormControl>
							<FormMessage />
						</FormItem>
					)}
				/>

				{posture === "Proactive" && (
					<FormField
						control={form.control}
						name="trigger.within"
						render={({ field }) => (
							<FormItem className="w-32">
								<FormLabel>Within (seconds)</FormLabel>
								<FormControl>
									<Input
										type="number"
										min={0}
										{...field}
										onChange={(e) => field.onChange(Number(e.target.value))}
									/>
								</FormControl>
								<FormMessage />
							</FormItem>
						)}
					/>
				)}
			</div>
		</div>
	);
};
