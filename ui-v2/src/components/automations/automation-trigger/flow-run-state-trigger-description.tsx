import {
	type AutomationTrigger,
	extractFlowRunStateProps,
	getAutomationTriggerEventPostureLabel,
	isEventTrigger,
	mapStateNameToStateType,
} from "@/components/automations/trigger-details";
import { FlowIconText } from "@/components/flows/flow-icon-text";
import { StateBadge } from "@/components/ui/state-badge";
import { TagBadgeGroup } from "@/components/ui/tag-badge-group";
import { secondsToString } from "@/utils";

type FlowRunStateTriggerDescriptionProps = {
	trigger: AutomationTrigger;
};

export const FlowRunStateTriggerDescription = ({
	trigger,
}: FlowRunStateTriggerDescriptionProps) => {
	if (!isEventTrigger(trigger)) {
		return null;
	}

	const { flowIds, tags, posture, states, time } =
		extractFlowRunStateProps(trigger);

	const postureLabel = getAutomationTriggerEventPostureLabel(posture);

	return (
		<div className="flex flex-wrap gap-1 items-center">
			<span>When any flow run</span>

			{flowIds.length > 0 && (
				<>
					<span>of flow</span>
					{flowIds.map((flowId, index) => (
						<span key={flowId} className="flex items-center gap-1">
							<FlowIconText flowId={flowId} />
							{index === flowIds.length - 2 && <span>or</span>}
						</span>
					))}
				</>
			)}

			{tags.length > 0 && (
				<>
					<span>with tags</span>
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
				<span>for {secondsToString(time)}</span>
			)}
		</div>
	);
};
