import { buildDeploymentDetailsQuery } from "@/api/deployments";
import { useSuspenseQuery } from "@tanstack/react-query";

import { DeploymentDetailsHeader } from "./deployment-details-header";
import { DeploymentDetailsTabs } from "./deployment-details-tabs";
import { DeploymentFlowLink } from "./deployment-flow-link";
import { DeploymentMetadata } from "./deployment-metadata";

type DeploymentDetailsPageProps = {
	id: string;
};

export const DeploymentDetailsPage = ({ id }: DeploymentDetailsPageProps) => {
	const { data } = useSuspenseQuery(buildDeploymentDetailsQuery(id));

	return (
		<div className="flex flex-col gap-4">
			<div className="flex align-middle justify-between">
				<div className="flex flex-col gap-2">
					<DeploymentDetailsHeader deployment={data} />
					<DeploymentFlowLink flowId={data.flow_id} />
				</div>
				<div className="flex align-middle gap-2">
					<div className="border border-red-400">{"<RunButton />"}</div>
					<div className="border border-red-400">{"<Actions />"}</div>
				</div>
			</div>
			<div className="grid gap-4" style={{ gridTemplateColumns: "3fr 1fr" }}>
				<div className="flex flex-col gap-5">
					<DeploymentDetailsTabs />
				</div>
				<div className="flex flex-col gap-3">
					<div className="border border-red-400">{"<SchedulesSection />"}</div>
					<div className="border border-red-400">{"<TriggerSection />"}</div>
					<hr />
					<DeploymentMetadata deployment={data} />
				</div>
			</div>
		</div>
	);
};
