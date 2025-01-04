import { ActionType } from "@/components/automations/automations-wizard/types";
import { Label } from "@/components/ui/label";
import {
	Select,
	SelectContent,
	SelectGroup,
	SelectItem,
	SelectLabel,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";

import { ChangeFlowRunStateFields } from "./change-flow-run-state-fields";

const AUTOMATION_ACTION_TYPES: Record<ActionType, string> = {
	"cancel-flow-run": "Cancel a flow run",
	"suspend-flow-run": "Suspend a flow run",
	"resume-flow-run": "Resume a flow run",
	"change-flow-run-state": "Change flow run's state",
	"run-deployment": "Run a deployment",
	"pause-deployment": "Pause a deployment",
	"resume-deployment": "Resume a deployment",
	"pause-work-queue": "Pause a work queue",
	"resume-work-queue": "Resume a work queue",
	"pause-work-pool": "Pause a work pool",
	"resume-work-pool": "Resume a work pool",
	"pause-automation": "Pause an automation",
	"resume-automation": "Resume an automation",
	"send-notification": "Send a notification",
};

type AutomationsActionSelectSelectProps = {
	actionType?: ActionType;
	actionFields?: Record<string, unknown>;
	onActionFieldsChange: (actionFields: Record<string, unknown>) => void;
	onChangeActionType: (actionType: ActionType) => void;
};

export const AutomationsActionSelect = ({
	actionType,
	actionFields,
	onActionFieldsChange,
	onChangeActionType,
}: AutomationsActionSelectSelectProps) => {
	return (
		<div className="row flex-col gap-4">
			<div>
				<Label htmlFor="automations-action-select">Action Type</Label>
				<Select value={actionType} onValueChange={onChangeActionType}>
					<SelectTrigger id="automations-action-select">
						<SelectValue placeholder="Select action" />
					</SelectTrigger>
					<SelectContent>
						<SelectGroup>
							<SelectLabel>Actions</SelectLabel>
							{Object.keys(AUTOMATION_ACTION_TYPES).map((key) => (
								<SelectItem key={key} value={key}>
									{AUTOMATION_ACTION_TYPES[key as ActionType]}
								</SelectItem>
							))}
						</SelectGroup>
					</SelectContent>
				</Select>
			</div>
			<AdditionalActionFields
				actionType={actionType}
				actionFields={actionFields}
				onActionFieldsChange={onActionFieldsChange}
			/>
		</div>
	);
};

type AdditionalActionFieldsProps = {
	actionType: ActionType | undefined;
	actionFields: Record<string, unknown> | undefined;
	onActionFieldsChange: (actionFields: Record<string, unknown>) => void;
};

const AdditionalActionFields = ({
	actionType,
	actionFields,
	onActionFieldsChange,
}: AdditionalActionFieldsProps) => {
	switch (actionType) {
		case "change-flow-run-state":
			return (
				<ChangeFlowRunStateFields
					values={actionFields as ChangeFlowRunStateFields}
					onChange={onActionFieldsChange}
				/>
			);
		case "run-deployment":
		case "pause-deployment":
		case "resume-deployment":
			return <div>TODO Deployment</div>;
		case "pause-work-queue":
		case "resume-work-queue":
			return <div>TODO Work Queue</div>;
		case "pause-work-pool":
		case "resume-work-pool":
			return <div>TODO Work pool</div>;
		case "pause-automation":
		case "resume-automation":
			return <div>TODO Automation</div>;
		case "send-notification":
			return <div>TODO send notification</div>;
		case "cancel-flow-run":
		case "suspend-flow-run":
		case "resume-flow-run":
		default:
			return null;
	}
};
