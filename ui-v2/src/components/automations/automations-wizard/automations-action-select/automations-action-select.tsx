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

const AUTOMATION_ACTION_TYPES = {
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
	"do-nothing": "Do nothing",
} as const;

export type AutomationActions = keyof typeof AUTOMATION_ACTION_TYPES;

type AutomationsActionSelectSelectProps = {
	onValueChange: (value: AutomationActions) => void;
	value?: AutomationActions;
};

export const AutomationsActionSelect = ({
	onValueChange,
	value,
}: AutomationsActionSelectSelectProps) => {
	return (
		<div className="row flex-col gap-4">
			<div>
				<Label htmlFor="automations-action-select">Action Type</Label>
				<Select value={value} onValueChange={onValueChange}>
					<SelectTrigger id="automations-action-select">
						<SelectValue placeholder="Select action" />
					</SelectTrigger>
					<SelectContent>
						<SelectGroup>
							<SelectLabel>Actions</SelectLabel>
							{Object.keys(AUTOMATION_ACTION_TYPES)
								.filter((key) => (key as AutomationActions) !== "do-nothing")
								.map((key) => (
									<SelectItem key={key} value={key}>
										{AUTOMATION_ACTION_TYPES[key as AutomationActions]}
									</SelectItem>
								))}
						</SelectGroup>
					</SelectContent>
				</Select>
			</div>
			<AdditionalActionFields actionType={value} />
		</div>
	);
};

type AdditionalActionFieldsProps = {
	actionType?: AutomationActions;
};
const AdditionalActionFields = ({
	actionType,
}: AdditionalActionFieldsProps) => {
	switch (actionType) {
		case "change-flow-run-state":
			return <div>TODO Flow Run state</div>;
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
		case "do-nothing":
		default:
			return null;
	}
};
