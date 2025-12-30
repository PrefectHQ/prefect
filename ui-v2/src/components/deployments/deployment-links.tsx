import type { Deployment } from "@/api/deployments";
import { FlowLink } from "@/components/flows/flow-link";
import { WorkPoolLink } from "@/components/work-pools/work-pool-link";
import { WorkQueueIconText } from "@/components/work-pools/work-queue-icon-text";

type DeploymentLinksProps = {
	deployment: Deployment;
};

export const DeploymentLinks = ({ deployment }: DeploymentLinksProps) => {
	return (
		<div className="flex items-center gap-4">
			<FlowLink flowId={deployment.flow_id} />
			{deployment.work_pool_name && (
				<WorkPoolLink workPoolName={deployment.work_pool_name} />
			)}
			{deployment.work_pool_name && deployment.work_queue_name && (
				<WorkQueueIconText
					workPoolName={deployment.work_pool_name}
					workQueueName={deployment.work_queue_name}
					showLabel
					showStatus
				/>
			)}
		</div>
	);
};
