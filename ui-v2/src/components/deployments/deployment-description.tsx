import type { Deployment } from "@/api/deployments";
import { LazyMarkdown } from "@/components/ui/lazy-markdown";

type DeploymentDescriptionProps = {
	deployment: Deployment;
};

export const DeploymentDescription = ({
	deployment,
}: DeploymentDescriptionProps) => (
	<div className="prose max-w-none">
		<LazyMarkdown>{deployment.description ?? ""}</LazyMarkdown>
	</div>
);
