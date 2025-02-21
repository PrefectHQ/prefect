import { Deployment } from "@/api/deployments";

import { Icon } from "@/components/ui/icons";
import { Typography } from "@/components/ui/typography";

import { Link } from "@tanstack/react-router";

type DeploymentCellProps = { deployment: Deployment };
export const DeploymentCell = ({ deployment }: DeploymentCellProps) => {
	return (
		<Link
			className="flex items-center gap-1"
			to="/deployments/deployment/$id"
			params={{ id: deployment.id }}
		>
			<Icon id="Rocket" className="h-4 w-4" />
			<Typography variant="bodySmall">{deployment.name}</Typography>
		</Link>
	);
};
