import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Deployment } from "@/api/deployments";

type DeploymentDescriptionProps = {
	deployment: Deployment;
};

export const DeploymentDescription = ({
	deployment,
}: DeploymentDescriptionProps) => (
	<div className="prose max-w-none">
		<Markdown remarkPlugins={[remarkGfm]}>{deployment.description}</Markdown>
	</div>
);
