import { useSuspenseQuery } from "@tanstack/react-query";
import { buildDeploymentDetailsQuery } from "@/api/deployments";
import { DeploymentActionHeader } from "./deployment-action-header";
import { DeploymentForm } from "./deployment-form";

type DeploymentDuplicatePageProps = {
	id: string;
};

export const DeploymentDuplicatePage = ({
	id,
}: DeploymentDuplicatePageProps) => {
	const { data } = useSuspenseQuery(buildDeploymentDetailsQuery(id));

	return (
		<div className="flex flex-col gap-4">
			<DeploymentActionHeader deployment={data} action="Duplicate" />
			<DeploymentForm deployment={data} mode="duplicate" />
		</div>
	);
};
