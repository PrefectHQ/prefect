import { useSuspenseQuery } from "@tanstack/react-query";
import { buildDeploymentDetailsQuery } from "@/api/deployments";
import { usePageTitle } from "@/hooks/use-page-title";
import { DeploymentActionHeader } from "./deployment-action-header";
import { DeploymentForm } from "./deployment-form";

type DeploymentEditPageProps = {
	id: string;
};

export const DeploymentEditPage = ({ id }: DeploymentEditPageProps) => {
	const { data } = useSuspenseQuery(buildDeploymentDetailsQuery(id));
	usePageTitle(`Edit Deployment: ${data.name}`);

	return (
		<div className="flex flex-col gap-4">
			<DeploymentActionHeader deployment={data} action="Edit" />
			<DeploymentForm deployment={data} mode="edit" />
		</div>
	);
};
