import { Typography } from "@/components/ui/typography";
import { pluralize } from "@/utils";
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

// TODO: Replace with actual DeploymentLink component from OSS-7455
const DeploymentLinkPlaceholder = ({
	deploymentId,
}: {
	deploymentId: string;
}) => (
	<Typography
		variant="bodySmall"
		className="font-medium"
		data-testid="deployment-link-placeholder"
	>
		{/* TODO: This should be a clickable link to /deployments/deployment/{deploymentId} */}
		Deployment-{deploymentId}
	</Typography>
);

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
			<Typography variant="bodySmall">When</Typography>

			{isAnyDeployment ? (
				<Typography variant="bodySmall">any deployment</Typography>
			) : (
				<>
					<Typography variant="bodySmall">
						{pluralize(deploymentIds.length, "deployment")}
					</Typography>
					{deploymentIds.map((deploymentId, index) => (
						<span key={deploymentId} className="flex items-center gap-1">
							<DeploymentLinkPlaceholder deploymentId={deploymentId} />
							{index === deploymentIds.length - 2 && (
								<Typography variant="bodySmall">or</Typography>
							)}
						</span>
					))}
				</>
			)}

			<Typography variant="bodySmall">{postureLabel}</Typography>
			<Typography variant="bodySmall">{statusLabel}</Typography>

			{posture === "Proactive" && time !== undefined && time > 0 && (
				<Typography variant="bodySmall">for {secondsToString(time)}</Typography>
			)}
		</div>
	);
};
