import type { Deployment } from "@/api/deployments";
import { WorkQueueLink } from "@/components//work-pools/work-queue-link";
import { FlowLink } from "@/components/flows/flow-link";
import { WorkPoolLink } from "@/components/work-pools/work-pool-link";

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
				<WorkQueueLink
					workPoolName={deployment.work_pool_name}
					workQueueName={deployment.work_queue_name}
				/>
			)}
		</div>
	);
};
