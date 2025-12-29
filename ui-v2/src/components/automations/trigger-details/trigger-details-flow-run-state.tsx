import type { components } from "@/api/prefect";
import { FlowLink } from "@/components/flows/flow-link";
import { StateBadge } from "@/components/ui/state-badge";
import { TagBadgeGroup } from "@/components/ui/tag-badge-group";
import { secondsToApproximateString } from "@/utils";
import {
	type AutomationTriggerEventPosture,
	getAutomationTriggerEventPostureLabel,
} from "./trigger-utils";

type StateType = components["schemas"]["StateType"];

type TriggerDetailsFlowRunStateProps = {
	flowIds: string[];
	tags: string[];
	posture: AutomationTriggerEventPosture;
	states: string[];
	time?: number;
};

/**
 * Maps a state name string to a StateType enum value.
 * Handles various state name formats (e.g., "Completed", "COMPLETED", "completed")
 * and maps them to the uppercase StateType values expected by StateBadge.
 */
function mapStateNameToStateType(stateName: string): StateType | null {
	const normalizedName = stateName.toUpperCase();

	const validStateTypes: StateType[] = [
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

	if (validStateTypes.includes(normalizedName as StateType)) {
		return normalizedName as StateType;
	}

	return null;
}

export const TriggerDetailsFlowRunState = ({
	flowIds,
	tags,
	posture,
	states,
	time,
}: TriggerDetailsFlowRunStateProps) => {
	const postureLabel = getAutomationTriggerEventPostureLabel(posture);

	return (
		<div className="flex flex-wrap gap-1 items-center">
			<span>When any flow run</span>

			{flowIds.length > 0 && (
				<>
					<span>of flow</span>
					{flowIds.map((flowId, index) => (
						<span key={flowId} className="flex items-center gap-1">
							<FlowLink flowId={flowId} />
							{index === flowIds.length - 2 && <span>or</span>}
						</span>
					))}
				</>
			)}

			{tags.length > 0 && (
				<>
					<span>with the tag</span>
					<TagBadgeGroup tags={tags} />
				</>
			)}

			<span>{postureLabel}</span>

			{states.length > 0 ? (
				states.map((state) => {
					const stateType = mapStateNameToStateType(state);
					if (stateType) {
						return <StateBadge key={state} type={stateType} />;
					}
					return null;
				})
			) : (
				<span>any state</span>
			)}

			{posture === "Proactive" && time !== undefined && time > 0 && (
				<span>for {secondsToApproximateString(time)}</span>
			)}
		</div>
	);
};
