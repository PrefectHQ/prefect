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
import { AutomationDeploymentCombobox } from "./automation-deployment-combobox";
import { PostureSelect } from "./posture-select";
import { StateMultiSelect } from "./state-multi-select";

type ResourceSpecification = Record<string, string | string[]>;
type MatchRelated = ResourceSpecification | ResourceSpecification[] | undefined;

const FLOW_RESOURCE_PREFIX = "prefect.flow.";
const TAG_RESOURCE_PREFIX = "prefect.tag.";
const DEPLOYMENT_RESOURCE_PREFIX = "prefect.deployment.";

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

function matchRelatedAsArray(
	matchRelated: MatchRelated,
): ResourceSpecification[] {
	if (!matchRelated) {
		return [];
	}

	return Array.isArray(matchRelated) ? matchRelated : [matchRelated];
}

function extractResourceIdsFromMatchRelated(
	matchRelated: MatchRelated,
	prefix: string,
): string[] {
	const resourceIds = matchRelatedAsArray(matchRelated).flatMap((match) => {
		const value = match["prefect.resource.id"];
		if (!value) {
			return [];
		}

		return Array.isArray(value) ? value : [value];
	});

	return resourceIds
		.filter((id) => id.startsWith(prefix))
		.map((id) => id.slice(prefix.length));
}

function extractFlowIdsFromMatchRelated(matchRelated: MatchRelated): string[] {
	return extractResourceIdsFromMatchRelated(matchRelated, FLOW_RESOURCE_PREFIX);
}

function extractTagsFromMatchRelated(matchRelated: MatchRelated): string[] {
	return extractResourceIdsFromMatchRelated(matchRelated, TAG_RESOURCE_PREFIX);
}

function extractDeploymentIdsFromMatchRelated(
	matchRelated: MatchRelated,
): string[] {
	return extractResourceIdsFromMatchRelated(
		matchRelated,
		DEPLOYMENT_RESOURCE_PREFIX,
	);
}

function buildMatchRelated(
	flowIds: string[],
	tags: string[],
	deploymentIds: string[],
): MatchRelated {
	const flowResourceIds = flowIds.map((id) => `${FLOW_RESOURCE_PREFIX}${id}`);
	const tagResourceIds = tags.map((tag) => `${TAG_RESOURCE_PREFIX}${tag}`);
	const deploymentResourceIds = deploymentIds.map(
		(id) => `${DEPLOYMENT_RESOURCE_PREFIX}${id}`,
	);

	if (
		flowResourceIds.length === 0 &&
		tagResourceIds.length === 0 &&
		deploymentResourceIds.length === 0
	) {
		return {};
	}

	const matchRelated: ResourceSpecification[] = [];

	if (flowResourceIds.length > 0 || tagResourceIds.length > 0) {
		// Since tags are hidden when flows are selected, only one type will be present
		const role = flowResourceIds.length > 0 ? "flow" : "tag";
		matchRelated.push({
			"prefect.resource.role": role,
			"prefect.resource.id": [...flowResourceIds, ...tagResourceIds],
		});
	}

	if (deploymentResourceIds.length > 0) {
		matchRelated.push({
			"prefect.resource.role": "deployment",
			"prefect.resource.id": deploymentResourceIds,
		});
	}

	return matchRelated.length === 1 ? matchRelated[0] : matchRelated;
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
	const selectedDeploymentIds =
		extractDeploymentIdsFromMatchRelated(matchRelated);

	const handleFlowToggle = (flowId: string) => {
		const currentFlowIds = selectedFlowIds;
		const newFlowIds = currentFlowIds.includes(flowId)
			? currentFlowIds.filter((id) => id !== flowId)
			: [...currentFlowIds, flowId];

		// Clear tags when flows are selected (Vue behavior)
		const newTags = newFlowIds.length > 0 ? [] : selectedTags;
		form.setValue(
			"trigger.match_related",
			buildMatchRelated(newFlowIds, newTags, selectedDeploymentIds),
		);
	};

	const handleTagsChange = (tags: string[]) => {
		form.setValue(
			"trigger.match_related",
			buildMatchRelated(selectedFlowIds, tags, selectedDeploymentIds),
		);
	};

	const handleDeploymentIdsChange = (deploymentIds: string[]) => {
		form.setValue(
			"trigger.match_related",
			buildMatchRelated(selectedFlowIds, selectedTags, deploymentIds),
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
				<FormLabel>Deployments</FormLabel>
				<FormControl>
					<AutomationDeploymentCombobox
						selectedDeploymentIds={selectedDeploymentIds}
						onSelectDeploymentIds={handleDeploymentIdsChange}
					/>
				</FormControl>
			</FormItem>

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
