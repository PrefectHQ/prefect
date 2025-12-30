import { Link } from "@tanstack/react-router";
import type { Deployment } from "@/api/deployments";
import { Icon } from "@/components/ui/icons";

type DeploymentIconTextProps = {
	deployment: Deployment;
};

export const DeploymentIconText = ({ deployment }: DeploymentIconTextProps) => {
	return (
		<Link
			className="flex items-center gap-1"
			to="/deployments/deployment/$id"
			params={{ id: deployment.id }}
		>
			<Icon id="Rocket" className="size-4" />
			{deployment.name}
		</Link>
	);
};
