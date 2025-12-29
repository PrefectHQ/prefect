import { DeploymentLink } from "@/components/deployments/deployment-link";
import { secondsToString } from "@/utils/seconds";
import {
	type AutomationTriggerEventPosture,
	getAutomationTriggerEventPostureLabel,
} from "./trigger-utils";

type DeploymentStatus = "ready" | "not_ready";

type TriggerDetailsDeploymentStatusProps = {
	deploymentIds: string[];
	posture: AutomationTriggerEventPosture;
	status: DeploymentStatus;
	time?: number;
};

function getDeploymentStatusLabel(status: DeploymentStatus): string {
	switch (status) {
		case "ready":
			return "ready";
		case "not_ready":
			return "not ready";
	}
}

export const TriggerDetailsDeploymentStatus = ({
	deploymentIds,
	posture,
	status,
	time,
}: TriggerDetailsDeploymentStatusProps) => {
	const isAnyDeployment = deploymentIds.length === 0;
	const postureLabel = getAutomationTriggerEventPostureLabel(posture);
	const statusLabel = getDeploymentStatusLabel(status);

	return (
		<div className="flex flex-wrap gap-1 items-center">
			<span>When</span>

			{isAnyDeployment ? (
				<span>any deployment</span>
			) : (
				deploymentIds.map((deploymentId, index) => (
					<span key={deploymentId} className="flex items-center gap-1">
						<DeploymentLink deploymentId={deploymentId} />
						{index === deploymentIds.length - 2 && <span>or</span>}
					</span>
				))
			)}

			<span>{postureLabel}</span>
			<span>{statusLabel}</span>

			{posture === "Proactive" && time !== undefined && time > 0 && (
				<span>for {secondsToString(time)}</span>
			)}
		</div>
	);
};
