import { Automation } from "@/api/automations";
import { Card } from "@/components/ui/card";
import { Typography } from "@/components/ui/typography";
type AutomationAction = Automation["actions"][number];

type ActionDetailsProps = {
	action: AutomationAction;
};
export const ActionDetails = ({ action }: ActionDetailsProps) => (
	<Card className="p-4 border-r-8">
		<ActionDetailsType action={action} />
	</Card>
);

export const ActionDetailsType = ({ action }: ActionDetailsProps) => {
	switch (action.type) {
		// Non-inferrable Actions
		case "do-nothing":
		case "cancel-flow-run":
		case "suspend-flow-run":
		case "resume-flow-run":
			return <NoninferredAction action={action} />;
		// Inferable actions
		case "run-deployment":
			return action.deployment_id && action.source == "selected" ? (
				"TODO"
			) : (
				<InferredAction action={action} />
			);
		case "pause-deployment":
		case "resume-deployment":
			return action.deployment_id && action.source == "selected" ? (
				"TODO"
			) : (
				<InferredAction action={action} />
			);
		case "pause-work-queue":
		case "resume-work-queue":
			return action.work_queue_id && action.source == "selected" ? (
				"TODO"
			) : (
				<InferredAction action={action} />
			);
		case "pause-automation":
		case "resume-automation":
			return action.automation_id && action.source == "selected" ? (
				"TODO"
			) : (
				<InferredAction action={action} />
			);
		case "pause-work-pool":
		case "resume-work-pool":
			return action.work_pool_id && action.source == "selected" ? (
				"TODO"
			) : (
				<InferredAction action={action} />
			);
		// Other actions
		case "send-notification":
			return "TODO";
		case "change-flow-run-state":
			return "TODO";
		case "call-webhook":
			return "TODO";
	}
};

const ACTION_TYPE_TO_STRING: Record<AutomationAction["type"], string> = {
	"cancel-flow-run": "Cancel flow run",
	"suspend-flow-run": "Suspend flow run",
	"resume-flow-run": "Resume a flow run",
	"change-flow-run-state": "Change state of a flow run",
	"run-deployment": "Run deployment",
	"pause-deployment": "Pause deployment",
	"resume-deployment": "Resume deployment",
	"pause-work-queue": "Pause work queue",
	"resume-work-queue": "Resume work queue",
	"pause-work-pool": "Pause work queue",
	"resume-work-pool": "Resume work queue",
	"pause-automation": "Pause automation",
	"resume-automation": "Resume automation",
	"call-webhook": "Call a custom webhook notification",
	"send-notification": "Send a notification",
	"do-nothing": "Do nothing",
} as const;

const NoninferredAction = ({ action }: ActionDetailsProps) => (
	<Typography variant="bodySmall">
		{`${ACTION_TYPE_TO_STRING[action.type]} from the triggering event`}
	</Typography>
);
const InferredAction = ({ action }: ActionDetailsProps) => (
	<Typography variant="bodySmall">
		{`${ACTION_TYPE_TO_STRING[action.type]} inferred from the triggering event`}
	</Typography>
);
