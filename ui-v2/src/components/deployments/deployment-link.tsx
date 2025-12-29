import { useSuspenseQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { Suspense } from "react";
import { buildDeploymentDetailsQuery } from "@/api/deployments";
import { Icon } from "@/components/ui/icons";
import { Skeleton } from "@/components/ui/skeleton";

type DeploymentLinkProps = {
	deploymentId: string;
};

export const DeploymentLink = ({ deploymentId }: DeploymentLinkProps) => {
	return (
		<Suspense fallback={<Skeleton className="h-4 w-full" />}>
			<DeploymentLinkImplementation deploymentId={deploymentId} />
		</Suspense>
	);
};

const DeploymentLinkImplementation = ({
	deploymentId,
}: DeploymentLinkProps) => {
	const { data: deployment } = useSuspenseQuery(
		buildDeploymentDetailsQuery(deploymentId),
	);

	return (
		<div className="flex items-center gap-1 text-xs">
			Deployment
			<Link
				to="/deployments/deployment/$id"
				params={{ id: deployment.id }}
				className="flex items-center gap-1"
			>
				<Icon id="Rocket" className="size-4" />
				{deployment.name}
			</Link>
		</div>
	);
};
