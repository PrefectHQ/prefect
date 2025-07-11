import { Link } from "@tanstack/react-router";
import type { Automation } from "@/api/automations";
import type { BlockDocument } from "@/api/block-documents";
import type { Deployment } from "@/api/deployments";
import type { components } from "@/api/prefect";
import type { WorkPool } from "@/api/work-pools";
import type { WorkQueue } from "@/api/work-queues";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
	Dialog,
	DialogContent,
	DialogHeader,
	DialogTitle,
	DialogTrigger,
} from "@/components/ui/dialog";
import { Icon, type IconId } from "@/components/ui/icons";
import { JsonInput } from "@/components/ui/json-input";
import { StateBadge } from "@/components/ui/state-badge";
import { Typography } from "@/components/ui/typography";
import { capitalize } from "@/utils";

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
	/** Default string if `block_type_name` is not found. */
	"send-notification": "Send a notification using",
	"do-nothing": "Do nothing",
} as const;
type ActionLabel =
	(typeof ACTION_TYPE_TO_STRING)[keyof typeof ACTION_TYPE_TO_STRING];

type AutomationAction = Automation["actions"][number];

type ActionDetailsProps = {
	action: AutomationAction;
	automationsMap: Map<string, Automation>;
	blockDocumentsMap: Map<string, BlockDocument>;
	deploymentsMap: Map<string, Deployment>;
	workPoolsMap: Map<string, WorkPool>;
	workQueuesMap: Map<string, WorkQueue>;
};
export const ActionDetails = ({
	action,
	automationsMap,
	blockDocumentsMap,
	deploymentsMap,
	workPoolsMap,
	workQueuesMap,
}: ActionDetailsProps) => (
	<Card className="p-4">
		<ActionDetailsType
			action={action}
			automationsMap={automationsMap}
			blockDocumentsMap={blockDocumentsMap}
			deploymentsMap={deploymentsMap}
			workPoolsMap={workPoolsMap}
			workQueuesMap={workQueuesMap}
		/>
	</Card>
);

const ActionDetailsType = ({
	action,
	automationsMap,
	blockDocumentsMap,
	deploymentsMap,
	workPoolsMap,
	workQueuesMap,
}: ActionDetailsProps) => {
	const label = ACTION_TYPE_TO_STRING[action.type];
	switch (action.type) {
		// Non-inferrable Actions
		case "cancel-flow-run":
		case "suspend-flow-run":
		case "resume-flow-run":
		case "call-webhook": // Not used
		case "do-nothing": // not used
			return <NoninferredAction label={label} />;
		// Inferable actions
		case "run-deployment":
			if (action.deployment_id && action.source === "selected") {
				const deployment = deploymentsMap.get(action.deployment_id);
				if (!deployment) {
					return <Typography>Deployment not found</Typography>;
				}
				return (
					<DeploymentActionDetails
						label={label}
						deployment={deployment}
						parameters={action.parameters}
						job_variables={action.job_variables}
					/>
				);
			}
			return <InferredAction label={label} />;
		case "pause-deployment":
		case "resume-deployment":
			if (action.deployment_id && action.source === "selected") {
				const deployment = deploymentsMap.get(action.deployment_id);
				if (!deployment) {
					return <Typography>Deployment not found</Typography>;
				}
				return (
					<DeploymentActionDetails label={label} deployment={deployment} />
				);
			}
			return <InferredAction label={label} />;
		case "pause-work-queue":
		case "resume-work-queue":
			if (action.work_queue_id && action.source === "selected") {
				const workQueue = workQueuesMap.get(action.work_queue_id);
				if (!workQueue) {
					return <Typography>Work queue not found</Typography>;
				}
				return <WorkQueueActionDetails label={label} workQueue={workQueue} />;
			}
			return <InferredAction label={label} />;
		case "pause-automation":
		case "resume-automation":
			if (action.automation_id && action.source === "selected") {
				const automation = automationsMap.get(action.automation_id);
				if (!automation) {
					return <Typography>Automation not found</Typography>;
				}
				return (
					<AutomationActionDetails label={label} automation={automation} />
				);
			}
			return <InferredAction label={label} />;
		case "pause-work-pool":
		case "resume-work-pool":
			if (action.work_pool_id && action.source === "selected") {
				const workPool = workPoolsMap.get(action.work_pool_id);
				if (!workPool) {
					return <Typography>Workpool not found</Typography>;
				}
				return <WorkPoolActionDetails label={label} workPool={workPool} />;
			}
			return <InferredAction label={label} />;
		// Other actions
		case "send-notification": {
			const blockDocument = blockDocumentsMap.get(action.block_document_id);
			if (!blockDocument) {
				return <Typography>Block document not found</Typography>;
			}
			return (
				<BlockDocumentActionDetails
					label={label}
					blockDocument={blockDocument}
				/>
			);
		}
		case "change-flow-run-state":
			return (
				<ChangeFlowRunStateActionDetails
					label={label}
					type={action.state}
					name={action.name}
				/>
			);
		default:
			return null;
	}
};

const ActionResource = ({ children }: { children: React.ReactNode }) => (
	<div className="text-sm flex items-center gap-1">{children}</div>
);

const ActionResourceName = ({
	iconId,
	name,
}: {
	name: string;
	iconId: IconId;
}) => (
	<div className="text-xs flex items-center">
		<Icon id={iconId} className="size-4 mr-1" />
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
	parameters?: Record<string, unknown> | null;
	job_variables?: Record<string, unknown> | null;
};
export const DeploymentActionDetails = ({
	label,
	deployment,
	parameters,
	job_variables,
}: DeploymentActionDetailsProps) => {
	return (
		<ActionResource>
			<label htmlFor={`${label}-${deployment.id}`}>{label}:</label>
			<Link
				to="/deployments/deployment/$id"
				params={{ id: deployment.id }}
				aria-label={deployment.name}
			>
				<ActionResourceName iconId="Rocket" name={deployment.name} />
			</Link>
			{parameters !== undefined && (
				<RunDeploymentJsonDialog title="Parameters" payload={parameters} />
			)}
			{job_variables !== undefined && (
				<RunDeploymentJsonDialog
					title="Job Variables"
					payload={job_variables}
				/>
			)}
		</ActionResource>
	);
};

type RunDeploymentJsonDialogProps = {
	title: string;
	payload: Record<string, unknown> | null | undefined;
};

const RunDeploymentJsonDialog = ({
	title,
	payload,
}: RunDeploymentJsonDialogProps) => {
	return (
		<Dialog>
			<DialogTrigger asChild>
				<Button variant="secondary" size="sm">
					Show {capitalize(title)}
				</Button>
			</DialogTrigger>
			<DialogContent aria-describedby={undefined}>
				<DialogHeader>
					<DialogTitle>{title}</DialogTitle>
				</DialogHeader>
				<JsonInput value={JSON.stringify(payload)} disabled />
			</DialogContent>
		</Dialog>
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
			<label htmlFor={`${label}-${automation.id}`}>{label}:</label>
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

type BlockDocumentActionDetailsProps = {
	label: ActionLabel;
	blockDocument: BlockDocument;
};
export const BlockDocumentActionDetails = ({
	label,
	blockDocument,
}: BlockDocumentActionDetailsProps) => {
	if (!blockDocument.name) {
		return <Typography>Block not found</Typography>;
	}

	const _label = blockDocument.block_type_name
		? `Send a ${blockDocument.block_type_name.toLowerCase()} using`
		: label;

	return (
		<ActionResource>
			<label htmlFor={`${label}-${blockDocument.id}`}>{_label}</label>
			<Link
				to="/blocks/block/$id"
				params={{ id: blockDocument.id }}
				aria-label={blockDocument.name}
			>
				<ActionResourceName iconId="Box" name={blockDocument.name} />
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
			<label htmlFor={`${label}-${workPool.id}`}>{label}:</label>
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
			<label htmlFor={`${label}-${workQueue.id}`}>{label}:</label>
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
