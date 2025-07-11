import { useSuspenseQuery } from "@tanstack/react-query";
import { buildDeploymentDetailsQuery } from "@/api/deployments";
import { DeploymentActionHeader } from "./deployment-action-header";
import { DeploymentForm } from "./deployment-form";

type DeploymentEditPageProps = {
	id: string;
};

export const DeploymentEditPage = ({ id }: DeploymentEditPageProps) => {
	const { data } = useSuspenseQuery(buildDeploymentDetailsQuery(id));

	return (
		<div className="flex flex-col gap-4">
			<DeploymentActionHeader deployment={data} action="Edit" />
			<DeploymentForm deployment={data} mode="edit" />
		</div>
	);
};
