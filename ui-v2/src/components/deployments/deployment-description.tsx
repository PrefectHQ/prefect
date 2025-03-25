import { Deployment } from "@/api/deployments";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";

type DeploymentDescriptionProps = {
	deployment: Deployment;
};

export const DeploymentDescription = ({
	deployment,
}: DeploymentDescriptionProps) => (
	<div className="prose">
		<Markdown remarkPlugins={[remarkGfm]}>{deployment.description}</Markdown>
	</div>
);
