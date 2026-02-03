import { Link } from "@tanstack/react-router";
import type { Deployment } from "@/api/deployments";
import { Icon } from "@/components/ui/icons";

type FlowRunDeploymentProps = { deployment: Deployment };
export const FlowRunDeployment = ({ deployment }: FlowRunDeploymentProps) => {
	return (
		<Link
			className="flex items-center gap-1"
			to="/deployments/deployment/$id"
			params={{ id: deployment.id }}
		>
			<p className="text-xs font-medium leading-none">Deployment</p>
			<Icon id="Rocket" className="size-4" />
			<p className="text-xs">{deployment.name}</p>
		</Link>
	);
};
