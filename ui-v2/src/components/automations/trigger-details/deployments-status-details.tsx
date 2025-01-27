import type { Deployment } from "@/api/deployments";
import { Icon } from "@/components/ui/icons";
import { pluralize } from "@/utils";
import { Link } from "@tanstack/react-router";
import humanizeDuration from "humanize-duration";
import {
	AUTOMATION_TRIGGER_EVENT_POSTURE_LABEL,
	type AutomationTrigger,
} from "./constants";

const DEPLOYMENT_STATUS_LABELS = {
	not_ready: "not ready",
	ready: "ready",
	disabled: "disabled",
} as const;
type DeploymentStatus = keyof typeof DEPLOYMENT_STATUS_LABELS;

const PREFECT_DEPLOYMENT_STATUS = {
	"prefect.deployment.ready": "ready",
	"prefect.deployment.not-ready": "not_ready",
	"prefect.deployment.disabled": "disabled",
} as const;
type PrefectDeploymentStatus = keyof typeof PREFECT_DEPLOYMENT_STATUS;

const getIsAnyDeployment = (trigger: AutomationTrigger) => {
	return trigger.match?.["prefect.resource.id"] === "prefect.deployment.*";
};

type DeploymentsListProps = { deployments: Array<Deployment> };
const DeploymentsList = ({ deployments }: DeploymentsListProps) => {
	return (
		<div className="flex gap-2">
			<div>{pluralize(deployments.length, "deployment")}</div>
			{deployments.map((deployment, i) => {
				return (
					<div key={deployment.id} className="flex items-center gap-1">
						<Link
							className="text-xs flex items-center"
							to="/deployments/deployment/$id"
							params={{ id: deployment.id }}
						>
							<Icon id="Rocket" className="h-4 w-4 mr-1" />
							{deployment.name}
						</Link>
						{i < deployments.length - 1 && "or"}
					</div>
				);
			})}
		</div>
	);
};

type DeploymentsStatusDetailsProps = {
	deployments: Array<Deployment>;
	trigger: AutomationTrigger;
};
export const DeploymentsStatusDetails = ({
	deployments,
	trigger,
}: DeploymentsStatusDetailsProps) => {
	const status = getDeploymentTriggerStatus(trigger);
	return (
		<div className="flex items-center gap-1 text-sm">
			When{" "}
			{getIsAnyDeployment(trigger) ? (
				"any deployment"
			) : (
				<DeploymentsList deployments={deployments} />
			)}{" "}
			{AUTOMATION_TRIGGER_EVENT_POSTURE_LABEL[trigger.posture]}{" "}
			{DEPLOYMENT_STATUS_LABELS[status]}
			{trigger.posture === "Proactive" &&
				` for ${humanizeDuration(trigger.within * 1_000)}`}
		</div>
	);
};

function getDeploymentTriggerStatus(
	trigger: AutomationTrigger,
): DeploymentStatus {
	// Reactive triggers respond to the presence of the expected events
	if (trigger.posture === "Reactive") {
		const status = trigger.expect?.[0];
		if (!status) {
			throw new Error("'expect' field expected");
		}
		return PREFECT_DEPLOYMENT_STATUS[status as PrefectDeploymentStatus];
	}
	// Proactive triggers respond to the absence of those expected events.
	const status = trigger.after?.[0];
	if (!status) {
		throw new Error("'after' field expected");
	}
	return PREFECT_DEPLOYMENT_STATUS[status as PrefectDeploymentStatus];
}
