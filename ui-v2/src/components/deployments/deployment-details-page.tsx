import { buildDeploymentDetailsQuery } from "@/api/deployments";
import { DeleteConfirmationDialog } from "@/components/ui/delete-confirmation-dialog";
import { useSuspenseQuery } from "@tanstack/react-query";

import { buildListAutomationsRelatedQuery } from "@/api/automations/automations";
import { DeploymentActionMenu } from "./deployment-action-menu";
import { DeploymentDetailsHeader } from "./deployment-details-header";
import { DeploymentDetailsTabs } from "./deployment-details-tabs";
import { DeploymentFlowLink } from "./deployment-flow-link";
import { DeploymentMetadata } from "./deployment-metadata";
import { DeploymentSchedules } from "./deployment-schedules/deployment-schedules";
import { DeploymentTriggers } from "./deployment-triggers";
import { RunFlowButton } from "./run-flow-button";
import { useDeleteDeploymentConfirmationDialog } from "./use-delete-deployment-confirmation-dialog";

type DeploymentDetailsPageProps = {
	id: string;
};

export const DeploymentDetailsPage = ({ id }: DeploymentDetailsPageProps) => {
	const { data: deployment } = useSuspenseQuery(
		buildDeploymentDetailsQuery(id),
	);

	const { data: automations } = useSuspenseQuery(
		buildListAutomationsRelatedQuery(`prefect.deployment.${id}`),
	);
	const [deleteConfirmationDialogState, confirmDelete] =
		useDeleteDeploymentConfirmationDialog();

	return (
		<>
			<div className="flex flex-col gap-4">
				<div className="flex align-middle justify-between">
					<div className="flex flex-col gap-2">
						<DeploymentDetailsHeader deployment={deployment} />
						<DeploymentFlowLink flowId={deployment.flow_id} />
					</div>
					<div className="flex align-middle gap-2">
						<RunFlowButton deployment={deployment} />
						<DeploymentActionMenu
							id={id}
							onDelete={() =>
								confirmDelete(deployment, { shouldNavigate: true })
							}
						/>
					</div>
				</div>
				<div className="grid gap-4" style={{ gridTemplateColumns: "3fr 1fr" }}>
					<div className="flex flex-col gap-5">
						<DeploymentDetailsTabs deployment={deployment} />
					</div>
					<div className="flex flex-col gap-3">
						<DeploymentSchedules deployment={deployment} />
						<DeploymentTriggers
							automations={automations}
							deployment={deployment}
						/>
						<hr />
						<DeploymentMetadata deployment={deployment} />
					</div>
				</div>
			</div>
			<DeleteConfirmationDialog {...deleteConfirmationDialogState} />
		</>
	);
};
