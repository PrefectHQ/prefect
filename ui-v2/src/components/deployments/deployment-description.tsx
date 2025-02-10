import { Deployment } from "@/api/deployments";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";

type DeploymentDescriptionProps = {
	deployment: Deployment;
};

export const DeploymentDescription = ({
	deployment,
}: DeploymentDescriptionProps) => (
	<Markdown className="prose" remarkPlugins={[remarkGfm]}>
		{deployment.description}
	</Markdown>
);
