import { Link } from "@tanstack/react-router";
import type { Deployment } from "@/api/deployments";
import { Icon } from "@/components/ui/icons";
import { Typography } from "@/components/ui/typography";

type FlowRunDeploymentProps = { deployment: Deployment };
export const FlowRunDeployment = ({ deployment }: FlowRunDeploymentProps) => {
	return (
		<Link
			className="flex items-center gap-1"
			to="/deployments/deployment/$id"
			params={{ id: deployment.id }}
		>
			<Typography variant="xsmall" className="font-medium leading-none">
				Deployment
			</Typography>
			<Icon id="Rocket" className="size-4" />
			<Typography variant="xsmall">{deployment.name}</Typography>
		</Link>
	);
};
