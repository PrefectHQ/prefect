import type { Automation } from "@/api/automations";
import type { Deployment } from "@/api/deployments";
import type { components } from "@/api/prefect";
import type { WorkPool } from "@/api/work-pools";
import type { WorkQueue } from "@/api/work-queues";
import { Card } from "@/components/ui/card";
import { Icon, IconId } from "@/components/ui/icons";
import { StateBadge } from "@/components/ui/state-badge";
import { Typography } from "@/components/ui/typography";
import {
	createFakeAutomation,
	createFakeDeployment,
	createFakeWorkPool,
	createFakeWorkQueue,
} from "@/mocks";
import { Link } from "@tanstack/react-router";

const ACTION_TYPE_TO_STRING = {
	"cancel-flow-run": "Cancel flow run",
	"suspend-flow-run": "Suspend flow run",
	"resume-flow-run": "Resume a flow run",
	"change-flow-run-state": "Change state of a flow run",
	"run-deployment": "Run deployment",
	"pause-deployment": "Pause deployment",
	"resume-deployment": "Resume deployment",
	"pause-work-queue": "Pause work queue",
	"resume-work-queue": "Resume work queue",
	"pause-work-pool": "Pause work pool",
	"resume-work-pool": "Resume work pool",
	"pause-automation": "Pause automation",
	"resume-automation": "Resume automation",
	"call-webhook": "Call a custom webhook notification",
	"send-notification": "Send a notification",
	"do-nothing": "Do nothing",
} as const;
type ActionLabel =
	(typeof ACTION_TYPE_TO_STRING)[keyof typeof ACTION_TYPE_TO_STRING];

type AutomationAction = Automation["actions"][number];

type ActionDetailsProps = {
	action: AutomationAction;
};
export const ActionDetails = ({ action }: ActionDetailsProps) => (
	<Card className="p-4">
		<ActionDetailsType action={action} />
	</Card>
);

export const ActionDetailsType = ({ action }: ActionDetailsProps) => {
	const label = ACTION_TYPE_TO_STRING[action.type];
	switch (action.type) {
		// Non-inferrable Actions
		case "do-nothing":
		case "cancel-flow-run":
		case "suspend-flow-run":
		case "resume-flow-run":
			return <NoninferredAction label={label} />;
		// Inferable actions
		case "run-deployment":
			return action.deployment_id && action.source == "selected" ? (
				"TODO"
			) : (
				<InferredAction label={label} />
			);
		case "pause-deployment":
		case "resume-deployment":
			return action.deployment_id && action.source == "selected" ? (
				// TODO: Pass a real deployment from API
				<DeploymentActionDetails
					label={label}
					deployment={createFakeDeployment()}
				/>
			) : (
				<InferredAction label={label} />
			);
		case "pause-work-queue":
		case "resume-work-queue":
			return action.work_queue_id && action.source == "selected" ? (
				// TODO: Pass a real work queue from API
				<WorkQueueActionDetails
					label={label}
					workQueue={createFakeWorkQueue()}
				/>
			) : (
				<InferredAction label={label} />
			);
		case "pause-automation":
		case "resume-automation":
			return action.automation_id && action.source == "selected" ? (
				// TODO: Pass a real automation from API
				<AutomationActionDetails
					label={label}
					automation={createFakeAutomation()}
				/>
			) : (
				<InferredAction label={label} />
			);
		case "pause-work-pool":
		case "resume-work-pool":
			return action.work_pool_id && action.source == "selected" ? (
				// TODO: Pass a real work pool from API
				<WorkPoolActionDetails label={label} workPool={createFakeWorkPool()} />
			) : (
				<InferredAction label={label} />
			);
		// Other actions
		case "send-notification":
			return "TODO";
		case "change-flow-run-state":
			return (
				<ChangeFlowRunStateActionDetails
					label={label}
					type={action.state}
					name={action.name}
				/>
			);
		case "call-webhook":
			return "TODO";
	}
};

const ActionResource = ({ children }: { children: React.ReactNode }) => (
	<div className="text-sm flex items-center gap-1">{children}</div>
);

const ActionResourceName = ({
	iconId,
	name,
}: { name: string; iconId: IconId }) => (
	<div className="text-xs flex items-center">
		<Icon id={iconId} className="h-4 w-4 mr-1" />
		{name}
	</div>
);

const NoninferredAction = ({ label }: { label: ActionLabel }) => (
	<Typography variant="bodySmall">{label} from the triggering event</Typography>
);

const InferredAction = ({ label }: { label: ActionLabel }) => (
	<Typography variant="bodySmall">
		{label} inferred from the triggering event
	</Typography>
);

type ChangeFlowRunStateActionDetailsProps = {
	label: ActionLabel;
	type: components["schemas"]["StateType"];
	name?: string | null;
};

export const ChangeFlowRunStateActionDetails = ({
	label,
	type,
	name,
}: ChangeFlowRunStateActionDetailsProps) => {
	return (
		<ActionResource>
			<InferredAction label={label} /> to <StateBadge type={type} name={name} />
		</ActionResource>
	);
};

// Selected resources
type DeploymentActionDetailsProps = {
	label: ActionLabel;
	deployment: Deployment;
};
export const DeploymentActionDetails = ({
	label,
	deployment,
}: DeploymentActionDetailsProps) => {
	return (
		<ActionResource>
			<label>{label}:</label>
			<Link
				to="/deployments/deployment/$id"
				params={{ id: deployment.id }}
				aria-label={deployment.name}
			>
				<ActionResourceName iconId="Rocket" name={deployment.name} />
			</Link>
		</ActionResource>
	);
};

type AutomationActionDetailsProps = {
	label: ActionLabel;
	automation: Automation;
};
export const AutomationActionDetails = ({
	label,
	automation,
}: AutomationActionDetailsProps) => {
	return (
		<ActionResource>
			<label>{label}:</label>
			<Link
				to="/automations/automation/$id"
				params={{ id: automation.id }}
				aria-label={automation.name}
			>
				<ActionResourceName iconId="Bot" name={automation.name} />
			</Link>
		</ActionResource>
	);
};

type WorkPoolActionDetailsProps = {
	label: ActionLabel;
	workPool: WorkPool;
};
export const WorkPoolActionDetails = ({
	label,
	workPool,
}: WorkPoolActionDetailsProps) => {
	return (
		<ActionResource>
			<label>{label}:</label>
			<Link
				to="/work-pools/work-pool/$workPoolName"
				params={{ workPoolName: workPool.name }}
				aria-label={workPool.name}
			>
				<ActionResourceName iconId="Cpu" name={workPool.name} />
			</Link>
		</ActionResource>
	);
};

type WorkQueueActionDetailsProps = {
	label: ActionLabel;
	workQueue: WorkQueue;
};
export const WorkQueueActionDetails = ({
	label,
	workQueue,
}: WorkQueueActionDetailsProps) => {
	return (
		<ActionResource>
			<label>{label}:</label>
			<Link
				to="/work-pools/work-pool/$workPoolName/queue/$workQueueName"
				params={{
					workPoolName: workQueue.name,
					workQueueName: workQueue.name,
				}}
				aria-label={workQueue.name}
			>
				<ActionResourceName iconId="Cpu" name={workQueue.name} />
			</Link>
		</ActionResource>
	);
};
